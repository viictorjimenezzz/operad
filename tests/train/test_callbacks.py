"""Per-callback unit tests for `operad.train.callbacks`."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest

from operad.benchmark.evaluate import EvalReport
from operad.train import (
    BestCheckpoint,
    Callback,
    EarlyStopping,
    GradClip,
    LearningRateLogger,
    MemoryRotation,
    PromptDrift,
)
from operad.train.report import EpochReport, TrainingReport


def _eval_report(summary: dict[str, float]) -> EvalReport:
    return EvalReport(rows=[], summary=summary)


class _FakeTrainer:
    """Stand-in for `Trainer` — exposes just the attributes callbacks read."""

    def __init__(self) -> None:
        self._should_stop = False
        self.optimizer = _FakeOptimizer()
        self.agent = _FakeAgent()
        self._last_batch_tape_entries = 0


class _FakeOptimizer:
    def __init__(self) -> None:
        self.param_groups: list[Any] = []


class _FakeAgent:
    def __init__(self) -> None:
        self.hash_content = "seed"


# ---------------------------------------------------------------------------
# Callback base class
# ---------------------------------------------------------------------------


async def test_callback_base_methods_are_noops() -> None:
    cb = Callback()
    t = _FakeTrainer()
    await cb.on_fit_start(t)  # type: ignore[arg-type]
    await cb.on_epoch_start(t, 0)  # type: ignore[arg-type]
    await cb.on_batch_start(t, None, 0)  # type: ignore[arg-type]
    await cb.on_batch_end(t, None, 0, 0.0)  # type: ignore[arg-type]
    await cb.on_epoch_end(t, EpochReport(epoch=0, train_loss=0.0))  # type: ignore[arg-type]
    await cb.on_validation_end(t, _eval_report({}))  # type: ignore[arg-type]
    await cb.on_fit_end(t, TrainingReport())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# EarlyStopping
# ---------------------------------------------------------------------------


async def test_early_stopping_mode_min_patience() -> None:
    es = EarlyStopping(monitor="loss", mode="min", patience=2, min_delta=0.0)
    t = _FakeTrainer()

    # improving: best resets each time, no stop
    for v in [0.9, 0.8, 0.7]:
        await es.on_validation_end(t, _eval_report({"loss": v}))  # type: ignore[arg-type]
    assert t._should_stop is False

    # stagnant for 3 calls (patience=2 means > 2 stale → stop after 3rd)
    await es.on_validation_end(t, _eval_report({"loss": 0.7}))  # type: ignore[arg-type]
    await es.on_validation_end(t, _eval_report({"loss": 0.7}))  # type: ignore[arg-type]
    assert t._should_stop is False
    await es.on_validation_end(t, _eval_report({"loss": 0.7}))  # type: ignore[arg-type]
    assert t._should_stop is True


async def test_early_stopping_mode_max_tracks_higher_is_better() -> None:
    es = EarlyStopping(monitor="acc", mode="max", patience=1, min_delta=0.0)
    t = _FakeTrainer()

    await es.on_validation_end(t, _eval_report({"acc": 0.5}))  # type: ignore[arg-type]
    await es.on_validation_end(t, _eval_report({"acc": 0.6}))  # type: ignore[arg-type]
    assert t._should_stop is False
    # stagnant twice
    await es.on_validation_end(t, _eval_report({"acc": 0.6}))  # type: ignore[arg-type]
    await es.on_validation_end(t, _eval_report({"acc": 0.6}))  # type: ignore[arg-type]
    assert t._should_stop is True


async def test_early_stopping_min_delta_blocks_tiny_improvements() -> None:
    es = EarlyStopping(monitor="loss", mode="min", patience=0, min_delta=0.1)
    t = _FakeTrainer()

    await es.on_validation_end(t, _eval_report({"loss": 1.0}))  # type: ignore[arg-type]
    # 0.99 is a "real" improvement but below min_delta=0.1 → counts as stale.
    await es.on_validation_end(t, _eval_report({"loss": 0.99}))  # type: ignore[arg-type]
    assert t._should_stop is True


async def test_early_stopping_ignores_nan_values() -> None:
    es = EarlyStopping(monitor="loss", mode="min", patience=0, min_delta=0.0)
    t = _FakeTrainer()

    await es.on_validation_end(t, _eval_report({"other": 0.5}))  # type: ignore[arg-type]
    assert t._should_stop is False


def test_early_stopping_rejects_invalid_config() -> None:
    with pytest.raises(ValueError):
        EarlyStopping(mode="best")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EarlyStopping(patience=-1)
    with pytest.raises(ValueError):
        EarlyStopping(min_delta=-1.0)


# ---------------------------------------------------------------------------
# BestCheckpoint (rejects bad mode; full integration is in test_trainer.py)
# ---------------------------------------------------------------------------


def test_best_checkpoint_rejects_bad_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        BestCheckpoint(tmp_path / "x.json", mode="best")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GradClip
# ---------------------------------------------------------------------------


def test_gradclip_rejects_nonpositive_max() -> None:
    with pytest.raises(ValueError):
        GradClip(max_severity=0.0)
    with pytest.raises(ValueError):
        GradClip(max_severity=-1.0)


async def test_gradclip_ignores_params_without_grad() -> None:
    from operad.optim.optimizer import ParamGroup

    class _P:
        grad = None
        path = "role"
        kind = "role"

    group = ParamGroup(params=[_P()])  # type: ignore[list-item]
    t = _FakeTrainer()
    t.optimizer.param_groups = [group]

    cb = GradClip(max_severity=0.2)
    # Should not raise even with grad=None.
    await cb.on_batch_end(t, None, 0, 0.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PromptDrift
# ---------------------------------------------------------------------------


async def test_prompt_drift_warns_over_threshold() -> None:
    cb = PromptDrift(max_hash_changes=2)
    t = _FakeTrainer()
    await cb.on_fit_start(t)  # type: ignore[arg-type]

    def _end(h: str, epoch: int) -> Any:
        t.agent.hash_content = h
        return EpochReport(epoch=epoch, train_loss=0.0, hash_content=h)

    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        # Threshold of 2: changes 1 and 2 are allowed; change 3 warns.
        await cb.on_epoch_end(t, _end("h1", 0))  # type: ignore[arg-type]  # 1
        await cb.on_epoch_end(t, _end("h2", 1))  # type: ignore[arg-type]  # 2
        assert not any(
            issubclass(w.category, RuntimeWarning) for w in ws
        )
        await cb.on_epoch_end(t, _end("h3", 2))  # type: ignore[arg-type]  # 3
        assert any(issubclass(w.category, RuntimeWarning) for w in ws)


def test_prompt_drift_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError):
        PromptDrift(max_hash_changes=-1)


# ---------------------------------------------------------------------------
# LearningRateLogger
# ---------------------------------------------------------------------------


async def test_learning_rate_logger_emits_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cb = LearningRateLogger()
    t = _FakeTrainer()
    caplog.set_level("INFO", logger="operad.train")

    await cb.on_epoch_end(
        t,  # type: ignore[arg-type]
        EpochReport(epoch=2, train_loss=0.0, lr=[0.5]),
    )

    assert any("lr=[0.5]" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# MemoryRotation
# ---------------------------------------------------------------------------


async def test_memory_rotation_warns_when_tape_large(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cb = MemoryRotation(max_tape_entries=5)
    t = _FakeTrainer()
    t._last_batch_tape_entries = 10

    caplog.set_level("WARNING", logger="operad.train")
    await cb.on_batch_end(t, None, 3, 0.0)  # type: ignore[arg-type]

    assert any("tape size 10" in r.getMessage() for r in caplog.records)


def test_memory_rotation_rejects_bad_threshold() -> None:
    with pytest.raises(ValueError):
        MemoryRotation(max_tape_entries=0)
