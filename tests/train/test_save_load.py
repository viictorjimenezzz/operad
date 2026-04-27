"""Offline tests for `Trainer.save` / `Trainer.load`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.data.loader import DataLoader
from operad.metrics.metric import MetricBase
from operad.optim.schedulers.lr import ConstantLR
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter, TextualGradient
from operad.train import Trainer, TrainingReport
from tests._helpers.fake_leaf import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


class _StubLoss(MetricBase):
    name: str = "stub_loss"

    async def score(
        self, predicted: Any, expected: Any
    ) -> float:
        return 0.5

    async def compute(
        self, predicted: Any, expected: Any
    ) -> tuple[float, TextualGradient]:
        return 0.5, TextualGradient.null_gradient()


class _StubOptimizer(Optimizer):
    def __init__(self, params: Any, *, lr: float = 1.0) -> None:
        super().__init__(params, defaults={"lr": lr})

    async def step(self) -> None:
        for p in self.param_groups[0].params:
            self.state.setdefault(p.path, {"count": 0})
            self.state[p.path]["count"] += 1

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        return None


async def _built_leaf(cfg: Any) -> FakeLeaf:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 0})
    leaf.mark_trainable(role=True)
    await leaf.abuild()
    return leaf


def _dataset(n: int = 2) -> Dataset[A, B]:
    entries = [
        Entry(input=A(text=f"x{i}"), expected_output=B(value=i))
        for i in range(n)
    ]
    return Dataset(entries, name="s", version="v1")


def _loader(ds: Dataset[A, B]) -> DataLoader[A, B]:
    return DataLoader(ds, batch_size=1)


async def test_save_produces_valid_json_bundle(
    cfg: Any, tmp_path: Path
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, _StubLoss())

    path = tmp_path / "bundle.json"
    trainer.save(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert "state" in data
    assert "optimizer_state" in data
    assert "scheduler_state" in data
    assert "report" in data
    assert "metadata" in data
    meta = data["metadata"]
    for key in ("operad_version", "python_version", "saved_at_iso"):
        assert key in meta


async def test_load_round_trips_optimizer_and_agent(
    cfg: Any, tmp_path: Path
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOptimizer(list(leaf.parameters()))
    await opt.step()  # give state_dict something to compare
    trainer = Trainer(leaf, opt, _StubLoss())

    path = tmp_path / "bundle.json"
    trainer.save(path)

    reloaded = Trainer.load(
        path,
        loss_fn=_StubLoss(),
        optimizer_factory=lambda a: _StubOptimizer(list(a.parameters())),
    )
    assert reloaded.agent.hash_content == leaf.hash_content
    assert reloaded.optimizer.state_dict() == opt.state_dict()


async def test_save_load_fit_continues(cfg: Any, tmp_path: Path) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, _StubLoss())
    await trainer.fit(_loader(_dataset()), epochs=1)
    assert trainer._last_report is not None

    path = tmp_path / "bundle.json"
    trainer.save(path)

    reloaded = Trainer.load(
        path,
        loss_fn=_StubLoss(),
        optimizer_factory=lambda a: _StubOptimizer(list(a.parameters())),
    )
    assert isinstance(reloaded._last_report, TrainingReport)
    report = await reloaded.fit(_loader(_dataset()), epochs=1)
    assert len(report.epochs) == 1


async def test_scheduler_state_round_trips(
    cfg: Any, tmp_path: Path
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOptimizer(list(leaf.parameters()), lr=0.5)
    sched = ConstantLR(opt)
    sched.step()
    sched.step()
    trainer = Trainer(leaf, opt, _StubLoss(), scheduler=sched)

    path = tmp_path / "bundle.json"
    trainer.save(path)

    reloaded = Trainer.load(
        path,
        loss_fn=_StubLoss(),
        optimizer_factory=lambda a: _StubOptimizer(list(a.parameters()), lr=0.5),
        scheduler_factory=lambda o: ConstantLR(o),
    )
    assert reloaded.scheduler is not None
    assert reloaded.scheduler.last_epoch == sched.last_epoch


async def test_save_scrubs_api_key(cfg: Any, tmp_path: Path) -> None:
    leaf = await _built_leaf(cfg)
    leaf.config = leaf.config.model_copy(update={"api_key": "sk-secret-xyz"})
    opt = _StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, _StubLoss())

    path = tmp_path / "bundle.json"
    trainer.save(path)
    assert "sk-secret-xyz" not in path.read_text(encoding="utf-8")


async def test_load_with_overlay_agent(cfg: Any, tmp_path: Path) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOptimizer(list(leaf.parameters()))
    trainer = Trainer(leaf, opt, _StubLoss())

    path = tmp_path / "bundle.json"
    trainer.save(path)

    shell = await _built_leaf(cfg)
    shell.role = "different-role"
    await shell.abuild()

    reloaded = Trainer.load(
        path,
        agent=shell,
        loss_fn=_StubLoss(),
        optimizer_factory=lambda a: _StubOptimizer(list(a.parameters())),
    )
    # Caller's shell is preserved, not overwritten by the frozen agent.
    assert reloaded.agent is shell
    assert reloaded.agent.role == "different-role"
