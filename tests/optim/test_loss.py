"""Offline tests for `operad.optim.losses`.

Covers `MetricLoss` (match, mismatch, custom hooks), `JudgeLoss`
(via a FakeLeaf critic), `SchemaLoss` (missing / wrong-typed /
perfect), `CompositeLoss` (aggregation, target_paths), and the
isinstance semantics of the `Loss` protocol vs. a pure `Metric`.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad.agents.reasoning.schemas import Candidate, Score
from operad.metrics.metric import Metric
from operad.metrics.metric import ExactMatch
from operad.optim.losses import (
    CompositeLoss,
    JudgeLoss,
    Loss,
    MetricLoss,
    SchemaLoss,
)
from operad.optim.parameter import TextualGradient
from tests._helpers.fake_leaf import A, B, FakeLeaf


class _RequiredFields(BaseModel):
    """Schema with a truly required field — `A`/`B` have defaults."""

    title: str
    count: int


# ---------------------------------------------------------------------------
# MetricLoss
# ---------------------------------------------------------------------------


async def test_loss_from_metric_exact_match_match():
    loss = MetricLoss(ExactMatch())
    predicted = A(text="hello")
    expected = A(text="hello")

    score, grad = await loss.compute(predicted, expected)

    assert score == 1.0
    assert grad.severity == 0.0
    assert grad.message == ""


async def test_loss_from_metric_exact_match_mismatch():
    loss = MetricLoss(ExactMatch())
    predicted = A(text="wrong")
    expected = A(text="right")

    score, grad = await loss.compute(predicted, expected)

    assert score == 0.0
    assert grad.severity == 1.0
    assert "wrong" in grad.message
    assert "right" in grad.message


async def test_loss_from_metric_custom_formatter_and_severity_fn():
    captured: dict[str, object] = {}

    def fmt(pred: BaseModel, exp: BaseModel | None, s: float) -> str:
        captured["called"] = True
        return f"CUSTOM:{s}"

    def sev(s: float) -> float:
        return 0.25

    loss = MetricLoss(
        ExactMatch(), gradient_formatter=fmt, severity_fn=sev
    )
    score, grad = await loss.compute(A(text="x"), A(text="y"))

    assert captured.get("called") is True
    assert grad.message == "CUSTOM:0.0"
    assert grad.severity == 0.25
    assert score == 0.0


async def test_loss_from_metric_rejects_none_expected():
    loss = MetricLoss(ExactMatch())
    with pytest.raises(ValueError):
        await loss.compute(A(text="x"), None)


async def test_loss_from_metric_name_passthrough():
    loss = MetricLoss(ExactMatch())
    assert loss.name == "exact_match"

    named = MetricLoss(ExactMatch(), name="custom")
    assert named.name == "custom"


# ---------------------------------------------------------------------------
# JudgeLoss
# ---------------------------------------------------------------------------


async def _build_fake_critic(cfg, score: float, rationale: str):
    critic = FakeLeaf(
        config=cfg,
        input=Candidate,
        output=Score,
        canned={"score": score, "rationale": rationale},
    )
    await critic.abuild()
    return critic


async def test_judge_loss_with_fake_critic(cfg):
    critic = await _build_fake_critic(cfg, 0.7, "close but not quite")
    loss = JudgeLoss(critic)

    score, grad = await loss.compute(B(value=1), None)

    assert score == pytest.approx(0.7)
    assert grad.message == "close but not quite"
    assert grad.severity == pytest.approx(0.3)


async def test_judge_loss_null_at_perfect_score(cfg):
    critic = await _build_fake_critic(cfg, 1.0, "perfect")
    loss = JudgeLoss(critic)

    score, grad = await loss.compute(B(value=1), None)

    assert score == 1.0
    assert grad.severity == 0.0
    assert grad.message == ""


async def test_judge_loss_severity_from_rationale(cfg):
    critic = await _build_fake_critic(cfg, 0.2, "bad output")
    loss = JudgeLoss(critic, severity_from="rationale")

    score, grad = await loss.compute(B(value=1), None)

    assert score == pytest.approx(0.2)
    assert grad.severity == 1.0
    assert grad.message == "bad output"


async def test_judge_loss_score_delegation(cfg):
    critic = await _build_fake_critic(cfg, 0.55, "mediocre")
    loss = JudgeLoss(critic)

    s = await loss.score(B(value=1), B(value=2))
    assert s == pytest.approx(0.55)


# ---------------------------------------------------------------------------
# SchemaLoss
# ---------------------------------------------------------------------------


async def test_schema_loss_missing_field():
    loss = SchemaLoss(_RequiredFields)
    # Construct an object lacking `count`.
    predicted = _RequiredFields.model_construct(title="hello")

    score, grad = await loss.compute(predicted, None)

    assert score < 1.0
    assert "count" in grad.by_field
    assert grad.severity > 0.0


async def test_schema_loss_wrong_type():
    class _Wrong(BaseModel):
        title: str = "x"
        count: str = "not a number"

    loss = SchemaLoss(_RequiredFields)
    predicted = _Wrong()

    score, grad = await loss.compute(predicted, None)

    assert score < 1.0
    assert "count" in grad.by_field


async def test_schema_loss_perfect():
    loss = SchemaLoss(_RequiredFields)
    predicted = _RequiredFields(title="ok", count=3)

    score, grad = await loss.compute(predicted, None)

    assert score == 1.0
    assert grad.severity == 0.0
    assert grad.by_field == {}


# ---------------------------------------------------------------------------
# CompositeLoss
# ---------------------------------------------------------------------------


class _ConstLoss:
    """Minimal `Loss` for CompositeLoss tests — avoids metric plumbing."""

    def __init__(
        self, *, name: str, score: float, message: str, target_paths=None
    ):
        self.name = name
        self._score = score
        self._message = message
        self._target_paths = list(target_paths or [])

    async def compute(self, predicted, expected):
        if self._score >= 1.0:
            return self._score, TextualGradient.null_gradient()
        return self._score, TextualGradient(
            message=self._message,
            severity=1.0 - self._score,
            target_paths=self._target_paths,
        )

    async def score(self, predicted, expected):
        return self._score


async def test_composite_loss_aggregates():
    l1 = _ConstLoss(name="l1", score=0.8, message="first")
    l2 = _ConstLoss(name="l2", score=0.4, message="second")
    comp = CompositeLoss([(l1, 0.7), (l2, 0.3)])

    score, grad = await comp.compute(A(text="x"), A(text="y"))

    assert score == pytest.approx(0.7 * 0.8 + 0.3 * 0.4)
    assert grad.severity == pytest.approx(0.7 * 0.2 + 0.3 * 0.6)
    assert grad.message == "first | second"


async def test_composite_loss_preserves_target_paths():
    l1 = _ConstLoss(
        name="l1", score=0.5, message="m1", target_paths=["role", "task"]
    )
    l2 = _ConstLoss(
        name="l2", score=0.5, message="m2", target_paths=["task", "rules[0]"]
    )
    comp = CompositeLoss([(l1, 1.0), (l2, 1.0)])

    _, grad = await comp.compute(A(text="x"), A(text="y"))

    assert grad.target_paths == ["role", "task", "rules[0]"]


async def test_composite_loss_merges_by_field():
    class _ByFieldLoss:
        name = "bf"

        async def compute(self, predicted, expected):
            return 0.5, TextualGradient(
                message="m",
                by_field={"title": "missing"},
                severity=0.5,
            )

        async def score(self, predicted, expected):
            return 0.5

    comp = CompositeLoss([(_ByFieldLoss(), 1.0)])
    _, grad = await comp.compute(A(text="x"), A(text="y"))

    assert grad.by_field == {"title": "missing"}


async def test_composite_loss_rejects_empty():
    with pytest.raises(ValueError):
        CompositeLoss([])


async def test_composite_loss_rejects_negative_weight():
    with pytest.raises(ValueError):
        CompositeLoss([(MetricLoss(ExactMatch()), -0.5)])


# ---------------------------------------------------------------------------
# Loss Protocol isinstance semantics
# ---------------------------------------------------------------------------


def test_pure_metric_is_not_a_loss():
    assert not isinstance(ExactMatch(), Loss)


def test_lifted_metric_is_a_loss():
    assert isinstance(MetricLoss(ExactMatch()), Loss)


def test_loss_is_a_metric():
    assert isinstance(MetricLoss(ExactMatch()), Metric)
    assert isinstance(SchemaLoss(_RequiredFields), Metric)
