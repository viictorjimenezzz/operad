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
    LRLogger,
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

    # stagnant: patience=2 means >= 2 stale → stop after 2nd non-improving call
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
    # patience=1: first stale call triggers stop
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


async def test_early_stopping_stops_at_exact_patience() -> None:
    """Regression: _stale >= patience, not > patience (off-by-one)."""
    es = EarlyStopping(monitor="loss", mode="min", patience=3, min_delta=0.0)
    t = _FakeTrainer()

    await es.on_validation_end(t, _eval_report({"loss": 1.0}))  # sets best
    for _ in range(2):
        await es.on_validation_end(t, _eval_report({"loss": 1.0}))  # stale 1, 2
    assert t._should_stop is False
    await es.on_validation_end(t, _eval_report({"loss": 1.0}))  # stale 3 → stop
    assert t._should_stop is True


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
    from operad.optim.optimizers.optimizer import ParamGroup

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
# LRLogger
# ---------------------------------------------------------------------------


async def test_learning_rate_logger_emits_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cb = LRLogger()
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


# ---------------------------------------------------------------------------
# Curriculum
# ---------------------------------------------------------------------------


from operad.data.loader import PermutableSampler
from operad.train import Curriculum


class _FakeLoader:
    def __init__(self, sampler: Any) -> None:
        self._sampler = sampler


class _CurriculumTrainer(_FakeTrainer):
    def __init__(self, severity_map: dict[int, float], sampler: Any) -> None:
        super().__init__()
        self.last_epoch_per_sample_severity = severity_map
        self.loader = _FakeLoader(sampler)


def _epoch_report() -> EpochReport:
    return EpochReport(epoch=0, train_loss=0.0)


async def test_curriculum_hard_first_orders_descending() -> None:
    sampler = PermutableSampler(3)
    t = _CurriculumTrainer({0: 0.1, 1: 0.9, 2: 0.5}, sampler)
    cb = Curriculum(mode="hard_first")
    await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert sampler._order == [1, 2, 0]


async def test_curriculum_easy_first_orders_ascending() -> None:
    sampler = PermutableSampler(3)
    t = _CurriculumTrainer({0: 0.1, 1: 0.9, 2: 0.5}, sampler)
    cb = Curriculum(mode="easy_first")
    await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert sampler._order == [0, 2, 1]


async def test_curriculum_anneal_hard_first_during_warmup() -> None:
    sampler = PermutableSampler(3)
    severity = {0: 0.1, 1: 0.9, 2: 0.5}
    t = _CurriculumTrainer(severity, sampler)
    cb = Curriculum(mode="anneal", warmup_epochs=2)
    # epoch 1 of 2 warmup: hard_first
    await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert sampler._order == [1, 2, 0]
    # epoch 2 of 2 warmup: still hard_first
    await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert sampler._order == [1, 2, 0]


async def test_curriculum_anneal_random_after_warmup() -> None:
    sampler = PermutableSampler(3)
    severity = {0: 0.1, 1: 0.9, 2: 0.5}
    t = _CurriculumTrainer(severity, sampler)
    cb = Curriculum(mode="anneal", warmup_epochs=1)
    # epoch 1: warmup (hard_first)
    await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert sampler._order == [1, 2, 0]
    # epoch 2: post-warmup, result is a valid permutation
    await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert sorted(sampler._order) == [0, 1, 2]


async def test_curriculum_uniform_severity_no_error() -> None:
    sampler = PermutableSampler(3)
    t = _CurriculumTrainer({0: 0.5, 1: 0.5, 2: 0.5}, sampler)
    cb = Curriculum(mode="hard_first")
    await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert sorted(sampler._order) == [0, 1, 2]  # valid permutation, no error


async def test_curriculum_warns_when_sampler_lacks_set_order() -> None:
    class _NoOrderSampler:
        def __iter__(self):
            return iter([])
        def __len__(self):
            return 0

    t = _CurriculumTrainer({0: 0.5}, _NoOrderSampler())
    cb = Curriculum(mode="hard_first")
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        await cb.on_epoch_end(t, _epoch_report())  # type: ignore[arg-type]
    assert any("set_order" in str(w.message) for w in ws)


def test_curriculum_rejects_invalid_mode() -> None:
    with pytest.raises(ValueError):
        Curriculum(mode="random")  # type: ignore[arg-type]


def test_curriculum_rejects_negative_warmup() -> None:
    with pytest.raises(ValueError):
        Curriculum(warmup_epochs=-1)
