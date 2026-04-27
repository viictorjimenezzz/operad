"""Training cassette record/replay tests (stream 5-2).

Validates that ``training_cassette_context`` produces byte-equal
``TrainingReport``s across a record phase and a replay phase, using a
fully offline setup (``FakeLeaf`` agent, deterministic stub loss and
optimizer — no real LLM calls).

Two tests:
- ``test_training_replay_byte_equal``: record then replay, assert
  identical report and final parameter values.
- ``test_training_replay_cassette_miss_on_rule_change``: modify the
  agent prompt between record and replay, assert ``TrainCassetteMiss``
  is raised naming the offending segment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field

from operad import Configuration
from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.data.loader import DataLoader
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter, TextualGradient
from operad.train import Trainer
from operad.utils.cassette import TrainCassetteMiss, training_cassette_context
from tests._helpers.fake_leaf import FakeLeaf


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class Q(BaseModel):
    text: str = Field(default="", description="A question.")


class R(BaseModel):
    text: str = Field(default="", description="A reply.")


# ---------------------------------------------------------------------------
# Stubs — deterministic, no LLM calls
# ---------------------------------------------------------------------------


class _FixedLoss:
    """Stub loss: always returns (0.5, severity-1 gradient)."""

    name = "fixed_loss"

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        return 0.5, TextualGradient(message="always improve", severity=1.0)

    async def score(self, predicted: BaseModel, expected: BaseModel | None) -> float:
        return 0.5


class _MutatingOptimizer(Optimizer):
    """Stub optimizer: appends ``_u`` to each trainable text param per step."""

    def __init__(self, params: Any) -> None:
        super().__init__(params)

    async def step(self) -> None:
        for group in self.param_groups:
            for p in group.params:
                if p.grad is not None and p.grad.severity > 0:
                    if isinstance(p.value, str):
                        p.write(p.value + "_u")

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        return None


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _cfg() -> Configuration:
    from operad.core.config import Sampling
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        sampling=Sampling(temperature=0.0, max_tokens=16),
    )


async def _make_agent(role: str = "base role") -> FakeLeaf:
    agent = FakeLeaf(config=_cfg(), input=Q, output=R, canned={"text": "ok"})
    agent.role = role
    agent.mark_trainable(role=True)
    await agent.abuild()
    return agent


def _make_dataset() -> Dataset[Q, R]:
    entries = [
        Entry(input=Q(text="q1"), expected_output=R(text="r1")),
        Entry(input=Q(text="q2"), expected_output=R(text="r2")),
    ]
    return Dataset(entries, name="tiny", version="v1")


def _make_loader(ds: Dataset[Q, R]) -> DataLoader[Q, R]:
    return DataLoader(ds, batch_size=2, shuffle=False)


def _make_trainer(agent: FakeLeaf) -> Trainer[Q, R]:
    opt = _MutatingOptimizer(list(agent.parameters()))
    return Trainer(agent, opt, _FixedLoss())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _normalize_report(d: Any) -> Any:
    """Strip timing fields and normalise NaN to a sentinel for comparison."""
    if isinstance(d, float) and d != d:  # NaN
        return "__nan__"
    if isinstance(d, dict):
        return {k: _normalize_report(v) for k, v in d.items() if k != "duration_s"}
    if isinstance(d, list):
        return [_normalize_report(x) for x in d]
    return d


async def _stub_backward(
    _t: Any,
    _grad: TextualGradient,
    *,
    parameters: Any = None,
    **_: Any,
) -> None:
    """Stub ``backward`` — writes a fixed severity-1 grad onto each param."""
    if parameters is None:
        return
    for p in parameters:
        p.grad = TextualGradient(message="improve", severity=1.0)


@pytest.mark.asyncio
async def test_training_replay_byte_equal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Record a 2-epoch run; replay it; assert byte-equal TrainingReport."""
    monkeypatch.setattr("operad.train.trainer.backward", _stub_backward)
    ds = _make_dataset()
    loader = _make_loader(ds)
    cassette_path = tmp_path / "run"

    # --- record phase ---
    agent_rec = await _make_agent()
    trainer_rec = _make_trainer(agent_rec)
    with training_cassette_context(cassette_path, mode="record"):
        report_rec = await trainer_rec.fit(loader, epochs=2)

    actual_path = cassette_path.with_suffix(".train.jsonl")
    assert actual_path.exists(), "cassette file must exist after record"

    # --- replay phase ---
    agent_rep = await _make_agent()
    trainer_rep = _make_trainer(agent_rep)
    with training_cassette_context(cassette_path, mode="replay"):
        report_rep = await trainer_rep.fit(loader, epochs=2)

    assert _normalize_report(report_rec.model_dump(mode="json")) == _normalize_report(
        report_rep.model_dump(mode="json")
    ), "replayed TrainingReport differs from recorded one"
    for (path_r, p_r), (path_p, p_p) in zip(
        agent_rec.named_parameters(), agent_rep.named_parameters()
    ):
        assert path_r == path_p
        assert p_r.value == p_p.value, f"param {path_r!r} diverged after replay"


@pytest.mark.asyncio
async def test_training_replay_cassette_miss_on_rule_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changing the agent's role between record and replay raises TrainCassetteMiss."""
    monkeypatch.setattr("operad.train.trainer.backward", _stub_backward)
    ds = _make_dataset()
    loader = _make_loader(ds)
    cassette_path = tmp_path / "run"

    agent_rec = await _make_agent(role="original role")
    with training_cassette_context(cassette_path, mode="record"):
        await _make_trainer(agent_rec).fit(loader, epochs=1)

    # Different role → different hash_content → key miss
    agent_rep = await _make_agent(role="completely different role")
    with pytest.raises(TrainCassetteMiss) as exc_info:
        with training_cassette_context(cassette_path, mode="replay"):
            await _make_trainer(agent_rep).fit(loader, epochs=1)

    assert "hash_agent" in str(exc_info.value)
