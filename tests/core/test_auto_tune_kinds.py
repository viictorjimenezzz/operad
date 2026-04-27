"""Tests for `Agent.auto_tune(kind=...)` dispatch."""

from __future__ import annotations

import random
from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.metrics.base import MetricBase
from operad.optim.parameter import TextualGradient
from operad.utils.ops import AppendRule


class _NullLoss:
    """Loss that always emits a null gradient, sidestepping backward()."""

    name: str = "null_loss"

    async def compute(
        self, predicted: Any, expected: Any
    ) -> tuple[float, TextualGradient]:
        return 0.5, TextualGradient.null_gradient()


pytestmark = pytest.mark.asyncio


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    value: int = 0


class _RuleCountLeaf(Agent[Q, R]):
    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        return R.model_construct(value=len(self.rules))


class _RuleCountMetric(MetricBase):
    name = "rule_count"

    def __init__(self, target: int) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


def _seed(cfg: Any) -> _RuleCountLeaf:
    s = _RuleCountLeaf(config=cfg, task="count rules")
    s.role = "counter"
    s.rules = []
    return s


def _dataset() -> list[tuple[Q, R]]:
    return [(Q(text="a"), R(value=3))] * 2


def _metric() -> _RuleCountMetric:
    return _RuleCountMetric(target=3)


async def test_auto_tune_kind_evo_unchanged(cfg: Any) -> None:
    seed = _seed(cfg)
    await seed.abuild()
    result = await seed.auto_tune(
        _dataset(),
        _metric(),
        kind="evo",
        mutations=[AppendRule(path="", rule="x")],
        population_size=2,
        generations=1,
        rng=random.Random(0),
    )
    assert isinstance(result, _RuleCountLeaf)
    assert result is not seed


async def test_auto_tune_kind_bogus_raises(cfg: Any) -> None:
    seed = _seed(cfg)
    await seed.abuild()
    with pytest.raises(ValueError, match="evo, textgrad, momentum, opro, ape"):
        await seed.auto_tune(
            _dataset(),
            _metric(),
            kind="bogus",  # type: ignore[arg-type]
        )


class _StubSGD:
    """Drop-in replacement for TextualGradientDescent that records calls."""

    needs_evaluator = False

    def __init__(self, params: Any, *, lr: float = 1.0) -> None:
        self.param_groups = [
            type("G", (), {"params": list(params), "lr": float(lr)})()
        ]
        self.state: dict[str, Any] = {}
        self.step_calls = 0

    async def step(self) -> None:
        self.step_calls += 1

    def zero_grad(self) -> None:
        return None

    def state_dict(self) -> dict[str, Any]:
        return {}

    def load_state_dict(self, sd: dict[str, Any]) -> None:
        return None


async def test_auto_tune_kind_textgrad_runs(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Substitute a no-op stub SGD so we exercise the trainer path without an LLM."""
    captured: dict[str, Any] = {}

    def _factory(params: Any, lr: float = 1.0, **kwargs: Any) -> _StubSGD:
        opt = _StubSGD(params, lr=lr)
        captured["opt"] = opt
        return opt

    monkeypatch.setattr(
        "operad.optim.optimizers.tgd.TextualGradientDescent", _factory
    )

    seed = _seed(cfg)
    await seed.abuild()
    result = await seed.auto_tune(
        _dataset(),
        _metric(),
        kind="textgrad",
        epochs=1,
        batch_size=1,
        loss=_NullLoss(),
    )
    assert isinstance(result, _RuleCountLeaf)
    assert captured["opt"].step_calls >= 0


async def test_auto_tune_kind_momentum_runs(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def _factory(params: Any, lr: float = 1.0, **kwargs: Any) -> _StubSGD:
        opt = _StubSGD(params, lr=lr)
        captured["opt"] = opt
        return opt

    monkeypatch.setattr(
        "operad.optim.optimizers.momentum.MomentumTextGrad", _factory
    )

    seed = _seed(cfg)
    await seed.abuild()
    result = await seed.auto_tune(
        _dataset(),
        _metric(),
        kind="momentum",
        epochs=1,
        batch_size=1,
        loss=_NullLoss(),
    )
    assert isinstance(result, _RuleCountLeaf)


async def test_auto_tune_kind_opro_runs(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def _factory(
        params: Any,
        lr: float = 1.0,
        *,
        objective_metric: Any = None,
        evaluator: Any = None,
        **kwargs: Any,
    ) -> _StubSGD:
        opt = _StubSGD(params, lr=lr)
        captured["opt"] = opt
        captured["evaluator"] = evaluator
        return opt

    monkeypatch.setattr("operad.optim.optimizers.opro.OPROOptimizer", _factory)

    seed = _seed(cfg)
    await seed.abuild()
    result = await seed.auto_tune(
        _dataset(),
        _metric(),
        kind="opro",
        epochs=1,
        batch_size=1,
        loss=_NullLoss(),
    )
    assert isinstance(result, _RuleCountLeaf)
    # Evaluator closure was supplied.
    assert captured["evaluator"] is not None


async def test_auto_tune_kind_ape_runs(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def _factory(
        params: Any,
        lr: float = 1.0,
        *,
        evaluator: Any = None,
        k: int = 4,
        **kwargs: Any,
    ) -> _StubSGD:
        opt = _StubSGD(params, lr=lr)
        captured["opt"] = opt
        captured["evaluator"] = evaluator
        captured["k"] = k
        return opt

    monkeypatch.setattr("operad.optim.optimizers.ape.APEOptimizer", _factory)

    seed = _seed(cfg)
    await seed.abuild()
    result = await seed.auto_tune(
        _dataset(),
        _metric(),
        kind="ape",
        epochs=1,
        batch_size=1,
        population_size=3,
        loss=_NullLoss(),
    )
    assert isinstance(result, _RuleCountLeaf)
    assert captured["k"] == 3
    assert captured["evaluator"] is not None


async def test_auto_tune_kind_textgrad_ignores_mutations_kwarg(
    cfg: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _factory(params: Any, lr: float = 1.0, **kwargs: Any) -> _StubSGD:
        return _StubSGD(params, lr=lr)

    monkeypatch.setattr(
        "operad.optim.optimizers.tgd.TextualGradientDescent", _factory
    )

    seed = _seed(cfg)
    await seed.abuild()
    # `mutations` is an evo-only kwarg; passing it to textgrad must not raise.
    result = await seed.auto_tune(
        _dataset(),
        _metric(),
        kind="textgrad",
        mutations=[AppendRule(path="", rule="x")],
        epochs=1,
        batch_size=1,
        loss=_NullLoss(),
    )
    assert isinstance(result, _RuleCountLeaf)
