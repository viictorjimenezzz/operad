"""`BestCheckpoint(save_optimizer=True)` + `thaw_pair` enable resume."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.core.freeze import thaw_pair
from operad.data.loader import DataLoader
from operad.runtime.observers import registry as obs_registry
from operad.train import BestCheckpoint, Trainer

from ..conftest import A, B, FakeLeaf
from .test_trainer import StubLoss, StubOptimizer


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    obs_registry.clear()
    yield
    obs_registry.clear()


async def _built_leaf(cfg: Any, role: str = "initial") -> FakeLeaf:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 0})
    leaf.role = role
    leaf.mark_trainable(role=True)
    await leaf.abuild()
    return leaf


def _dataset(n: int = 1) -> Dataset[A, B]:
    entries = [
        Entry(input=A(text=f"x{i}"), expected_output=B(value=i))
        for i in range(n)
    ]
    return Dataset(entries, name="stub", version="v1")


def _loader(ds: Dataset[A, B]) -> DataLoader[A, B]:
    return DataLoader(ds, batch_size=1)


async def test_best_checkpoint_save_optimizer_persists_opt_state(
    cfg: Any, tmp_path: Path
) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss(scores=[0.9, 0.5, 0.1])
    opt = StubOptimizer(list(leaf.parameters()))
    # Seed non-trivial optimizer state so equality is meaningful post-thaw.
    for p in opt.param_groups[0].params:
        p.momentum_state = {"running_summary": "two-updates"}
        opt.state[p.path] = {"step_count": 7}

    ckpt_path = tmp_path / "best.json"
    trainer = Trainer(
        leaf,
        opt,
        loss,
        callbacks=[
            BestCheckpoint(
                ckpt_path,
                monitor="stub_loss",
                mode="min",
                save_optimizer=True,
            )
        ],
    )

    await trainer.fit(_loader(_dataset()), val_ds=_dataset(), epochs=3)

    assert ckpt_path.exists()
    reloaded_agent, opt_state = thaw_pair(ckpt_path)
    assert opt_state is not None
    assert reloaded_agent.hash_content == leaf.hash_content

    fresh = StubOptimizer(list(reloaded_agent.parameters()))
    fresh.load_state_dict(opt_state)
    assert fresh.state_dict() == opt.state_dict()


async def test_best_checkpoint_default_omits_optimizer_state(
    cfg: Any, tmp_path: Path
) -> None:
    leaf = await _built_leaf(cfg)
    loss = StubLoss(scores=[0.9, 0.5])
    opt = StubOptimizer(list(leaf.parameters()))
    ckpt_path = tmp_path / "best.json"
    trainer = Trainer(
        leaf,
        opt,
        loss,
        callbacks=[BestCheckpoint(ckpt_path, monitor="stub_loss", mode="min")],
    )

    await trainer.fit(_loader(_dataset()), val_ds=_dataset(), epochs=2)

    _, opt_state = thaw_pair(ckpt_path)
    assert opt_state is None


async def test_resume_training_from_checkpoint(
    cfg: Any, tmp_path: Path
) -> None:
    leaf = await _built_leaf(cfg)
    # Decreasing val_loss so the metric "continues improving" after resume.
    loss = StubLoss(scores=[0.9, 0.7, 0.5, 0.3, 0.1])
    opt = StubOptimizer(list(leaf.parameters()))
    ckpt_path = tmp_path / "best.json"
    trainer = Trainer(
        leaf,
        opt,
        loss,
        callbacks=[
            BestCheckpoint(
                ckpt_path,
                monitor="stub_loss",
                mode="min",
                save_optimizer=True,
            )
        ],
    )

    phase1 = await trainer.fit(_loader(_dataset()), val_ds=_dataset(), epochs=2)
    best_after_phase1 = min(
        r.val_loss for r in phase1.epochs if r.val_loss is not None
    )

    reloaded, opt_state = thaw_pair(ckpt_path)
    assert opt_state is not None

    resumed_opt = StubOptimizer(list(reloaded.parameters()))
    resumed_opt.load_state_dict(opt_state)
    # Continuing the score sequence from where phase 1 stopped.
    resumed_loss = StubLoss(scores=[0.05])
    resumed_trainer = Trainer(
        reloaded,
        resumed_opt,
        resumed_loss,
        callbacks=[
            BestCheckpoint(
                ckpt_path,
                monitor="stub_loss",
                mode="min",
                save_optimizer=True,
            )
        ],
    )

    phase2 = await resumed_trainer.fit(
        _loader(_dataset()), val_ds=_dataset(), epochs=1
    )
    best_after_phase2 = min(
        r.val_loss for r in phase2.epochs if r.val_loss is not None
    )

    assert best_after_phase2 < best_after_phase1
