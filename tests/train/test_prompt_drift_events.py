"""`PromptDrift` emits an `AlgorithmEvent` per epoch for the dashboard timeline."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.data.loader import DataLoader
from operad.metrics.metric import MetricBase
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter, TextualGradient
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import registry as obs_registry
from operad.train import PromptDrift, Trainer
from tests._helpers.fake_leaf import A, B, FakeLeaf


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    obs_registry.clear()
    yield
    obs_registry.clear()


class _StubLoss(MetricBase):
    def __init__(self) -> None:
        self.name = "stub"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        return 0.5

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        return 0.5, TextualGradient.null_gradient()


class _MutatingOptimizer(Optimizer):
    """Rewrites `role` on each step so `hash_content` changes."""

    def __init__(self, params: Any, *, mutate_agent: Any) -> None:
        super().__init__(params, defaults={"lr": 1.0})
        self.step_calls = 0
        self._mutate_agent = mutate_agent

    async def step(self) -> None:
        self.step_calls += 1
        self._mutate_agent.role = f"role-v{self.step_calls}"

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        return None


class _EventCollector:
    def __init__(self) -> None:
        self.events: list[AlgorithmEvent] = []

    async def on_event(self, event: Any) -> None:
        if isinstance(event, AlgorithmEvent):
            self.events.append(event)


async def _built_leaf(cfg: Any) -> FakeLeaf:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 0})
    leaf.role = "seed role"
    leaf.mark_trainable(role=True)
    await leaf.abuild()
    return leaf


def _dataset() -> Dataset[A, B]:
    return Dataset(
        [Entry(input=A(text="x"), expected_output=B(value=0))],
        name="stub",
        version="v1",
    )


async def test_prompt_drift_emits_iteration_event_per_epoch(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    opt = _MutatingOptimizer(list(leaf.parameters()), mutate_agent=leaf)
    trainer = Trainer(leaf, opt, _StubLoss(), callbacks=[PromptDrift()])

    collector = _EventCollector()
    obs_registry.register(collector)
    try:
        await trainer.fit(DataLoader(_dataset(), batch_size=1), epochs=3)
    finally:
        obs_registry.unregister(collector)

    drift_events = [
        e
        for e in collector.events
        if e.algorithm_path == "PromptDrift" and e.kind == "iteration"
    ]
    assert len(drift_events) == 3
    for i, e in enumerate(drift_events):
        assert e.payload["epoch"] == i
        assert isinstance(e.payload["before_text"], str)
        assert isinstance(e.payload["after_text"], str)
        assert isinstance(e.payload["changes"], list)
        assert isinstance(e.payload["changed_params"], list)
        assert isinstance(e.payload["delta_count"], int)
    assert drift_events[0].payload["before_text"] != drift_events[0].payload["after_text"]


async def test_prompt_drift_records_changed_param_paths(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    opt = _MutatingOptimizer(list(leaf.parameters()), mutate_agent=leaf)
    trainer = Trainer(leaf, opt, _StubLoss(), callbacks=[PromptDrift()])

    collector = _EventCollector()
    obs_registry.register(collector)
    try:
        await trainer.fit(DataLoader(_dataset(), batch_size=1), epochs=2)
    finally:
        obs_registry.unregister(collector)

    drift = [
        e for e in collector.events
        if e.algorithm_path == "PromptDrift" and e.kind == "iteration"
    ]
    assert drift[0].payload["delta_count"] >= 1
    assert "role" in drift[0].payload["changed_params"]


async def test_prompt_drift_emit_every_skips_off_epochs(cfg: Any) -> None:
    leaf = await _built_leaf(cfg)
    opt = _MutatingOptimizer(list(leaf.parameters()), mutate_agent=leaf)
    trainer = Trainer(
        leaf, opt, _StubLoss(), callbacks=[PromptDrift(emit_every=2)]
    )
    collector = _EventCollector()
    obs_registry.register(collector)
    try:
        await trainer.fit(DataLoader(_dataset(), batch_size=1), epochs=4)
    finally:
        obs_registry.unregister(collector)

    drift = [
        e for e in collector.events
        if e.algorithm_path == "PromptDrift" and e.kind == "iteration"
    ]
    assert [e.payload["epoch"] for e in drift] == [0, 2]
