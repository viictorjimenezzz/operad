"""`Callback` base class and the standard concrete callbacks.

`Callback` is a concrete class with seven async no-op lifecycle hooks;
users subclass and override the ones they care about. Concrete
implementations here cover the canonical PyTorch-Lightning surface:
early stopping, best checkpointing, textual-gradient clipping, drift
warnings, LR logging, and a tape-size guardrail.

Callbacks are invoked by `Trainer` in insertion order. A callback that
wants to halt training sets ``trainer._should_stop = True``; `Trainer`
checks the flag at the end of every epoch.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..benchmark.evaluate import EvalReport
from ..core.freeze import freeze_agent
from ..data.loader import Batch
from ..runtime.observers.base import _RUN_ID, emit_algorithm_event
from .report import EpochReport, TrainingReport

if TYPE_CHECKING:
    from .trainer import Trainer


_LOGGER = logging.getLogger("operad.train")


class Callback:
    """Base class for every `Trainer` callback.

    Every hook is an async no-op; subclasses override only what they need.
    """

    async def on_fit_start(self, trainer: "Trainer[Any, Any]") -> None:
        return None

    async def on_epoch_start(
        self, trainer: "Trainer[Any, Any]", epoch: int
    ) -> None:
        return None

    async def on_batch_start(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
    ) -> None:
        return None

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
        loss: float,
    ) -> None:
        return None

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        return None

    async def on_validation_end(
        self, trainer: "Trainer[Any, Any]", report: EvalReport
    ) -> None:
        return None

    async def on_fit_end(
        self, trainer: "Trainer[Any, Any]", report: TrainingReport
    ) -> None:
        return None


def _better(a: float, b: float, mode: Literal["min", "max"]) -> bool:
    """True when ``a`` improves over ``b`` under ``mode``."""
    if math.isnan(a):
        return False
    if math.isnan(b):
        return True
    return a < b if mode == "min" else a > b


def _extract_metric(report: EvalReport, monitor: str) -> float:
    """Pull ``monitor`` off ``report.summary`` with NaN fallback."""
    return float(report.summary.get(monitor, float("nan")))


class EarlyStopping(Callback):
    """Stop training when the monitored metric stops improving.

    Tracks the best value seen on `on_validation_end`. When the metric
    fails to improve by at least ``min_delta`` for ``patience``
    consecutive validations, the callback sets
    ``trainer._should_stop = True``.
    """

    def __init__(
        self,
        monitor: str = "val_loss",
        mode: Literal["min", "max"] = "min",
        patience: int = 3,
        min_delta: float = 1e-4,
    ) -> None:
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode!r}")
        if patience < 0:
            raise ValueError("patience must be non-negative")
        if min_delta < 0:
            raise ValueError("min_delta must be non-negative")
        self.monitor = monitor
        self.mode = mode
        self.patience = patience
        self.min_delta = min_delta
        self._best: float = float("inf") if mode == "min" else float("-inf")
        self._stale: int = 0

    async def on_validation_end(
        self, trainer: "Trainer[Any, Any]", report: EvalReport
    ) -> None:
        current = _extract_metric(report, self.monitor)
        if math.isnan(current):
            return
        delta = (
            self._best - current if self.mode == "min" else current - self._best
        )
        if delta > self.min_delta:
            self._best = current
            self._stale = 0
            return
        self._stale += 1
        if self._stale >= self.patience:
            trainer._should_stop = True


class BestCheckpoint(Callback):
    """Freeze the agent to disk whenever the monitored metric improves.

    When ``save_optimizer=True`` the trainer's optimizer state is
    persisted alongside the agent so training can resume exactly via
    :func:`operad.core.thaw_pair` + ``optimizer.load_state_dict``.
    """

    def __init__(
        self,
        path: str | Path,
        monitor: str = "val_loss",
        mode: Literal["min", "max"] = "min",
        save_optimizer: bool = False,
    ) -> None:
        if mode not in ("min", "max"):
            raise ValueError(f"mode must be 'min' or 'max', got {mode!r}")
        self.path = Path(path)
        self.monitor = monitor
        self.mode = mode
        self.save_optimizer = bool(save_optimizer)
        self._best: float = float("inf") if mode == "min" else float("-inf")

    async def on_validation_end(
        self, trainer: "Trainer[Any, Any]", report: EvalReport
    ) -> None:
        current = _extract_metric(report, self.monitor)
        if math.isnan(current):
            return
        if not _better(current, self._best, self.mode):
            return
        self._best = current
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.save_optimizer:
            freeze_agent(
                trainer.agent, self.path, optimizer=trainer.optimizer
            )
        else:
            freeze_agent(trainer.agent, self.path)


class GradClip(Callback):
    """Cap ``param.grad.severity`` in place before `optimizer.step()`."""

    def __init__(self, max_severity: float = 0.5) -> None:
        if max_severity <= 0:
            raise ValueError("max_severity must be positive")
        self.max_severity = max_severity

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
        loss: float,
    ) -> None:
        for group in trainer.optimizer.param_groups:
            for p in group.params:
                if p.grad is not None and p.grad.severity > self.max_severity:
                    p.grad = p.grad.model_copy(
                        update={"severity": self.max_severity}
                    )


class PromptDrift(Callback):
    """Warn when ``agent.hash_content`` changes too many times in a fit.

    Also emits an `AlgorithmEvent(kind="iteration", algorithm_path="PromptDrift")`
    every ``emit_every`` epochs so the dashboard can render prompt text diffs.
    """

    def __init__(
        self,
        max_hash_changes: int = 5,
        *,
        emit_every: int = 1,
    ) -> None:
        if max_hash_changes < 0:
            raise ValueError("max_hash_changes must be non-negative")
        if emit_every < 1:
            raise ValueError("emit_every must be >= 1")
        self.max_hash_changes = max_hash_changes
        self.emit_every = emit_every
        self._last_hash: str | None = None
        self._changes: int = 0
        self._warned: bool = False
        self._prev_values: dict[str, str] = {}

    def _snapshot_values(self, trainer: "Trainer[Any, Any]") -> dict[str, str]:
        values: dict[str, str] = {}
        named = getattr(trainer.agent, "named_parameters", None)
        if not callable(named):
            return values
        try:
            for path, param in named():
                values[path] = repr(getattr(param, "value", None))
        except Exception:
            return {}
        return values

    async def on_fit_start(self, trainer: "Trainer[Any, Any]") -> None:
        self._last_hash = trainer.agent.hash_content
        self._changes = 0
        self._warned = False
        self._prev_values = self._snapshot_values(trainer)

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        h = report.hash_content
        if self._last_hash is not None and h != self._last_hash:
            self._changes += 1
        self._last_hash = h

        current_values = self._snapshot_values(trainer)
        changed_params = sorted(
            path
            for path, value in current_values.items()
            if value != self._prev_values.get(path)
        )
        changes = [
            {
                "path": path,
                "before_text": self._prev_values.get(path, ""),
                "after_text": current_values.get(path, ""),
            }
            for path in changed_params
        ]
        selected = changes[0] if changes else None
        self._prev_values = current_values

        if self.emit_every > 0 and (report.epoch % self.emit_every) == 0:
            await emit_algorithm_event(
                "iteration",
                algorithm_path="PromptDrift",
                payload={
                    "epoch": int(report.epoch),
                    "before_text": selected["before_text"] if selected else "",
                    "after_text": selected["after_text"] if selected else "",
                    "selected_path": selected["path"] if selected else "",
                    "changes": changes,
                    "changed_params": changed_params,
                    "delta_count": len(changed_params),
                },
            )

        if self._changes > self.max_hash_changes and not self._warned:
            warnings.warn(
                f"agent hash_content changed {self._changes} times, "
                f"exceeding threshold {self.max_hash_changes}",
                RuntimeWarning,
                stacklevel=2,
            )
            self._warned = True


class LearningRateLogger(Callback):
    """Log each epoch's per-group LRs at INFO."""

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        _LOGGER.info("epoch=%d lr=%s", report.epoch, report.lr)


class MemoryRotation(Callback):
    """Warn when a batch's tape(s) recorded more than ``max_tape_entries``."""

    def __init__(self, max_tape_entries: int = 10_000) -> None:
        if max_tape_entries < 1:
            raise ValueError("max_tape_entries must be >= 1")
        self.max_tape_entries = max_tape_entries

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: Batch[Any, Any],
        step: int,
        loss: float,
    ) -> None:
        total = trainer._last_batch_tape_entries
        if total > self.max_tape_entries:
            _LOGGER.warning(
                "batch %d tape size %d exceeds threshold %d",
                step,
                total,
                self.max_tape_entries,
            )


EarlyStoppingSpec = EarlyStopping


def _row_id(predicted: Any) -> str:
    """Stable 16-hex key derived from sorted JSON of ``predicted``.

    Both the `HumanFeedbackCallback` (which holds dicts from the eval
    report) and the `HumanFeedbackLoss` (which holds Pydantic models)
    must agree on this hash, so we always reduce to a dict via
    ``model_dump(mode="json")`` before serialising with
    ``sort_keys=True``.
    """
    try:
        if hasattr(predicted, "model_dump"):
            dumped = predicted.model_dump(mode="json")
        else:
            dumped = predicted
        payload = json.dumps(dumped, sort_keys=True, default=str)
    except Exception:
        payload = repr(predicted)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _to_json_safe(x: Any) -> Any:
    if x is None:
        return None
    if hasattr(x, "model_dump"):
        try:
            return x.model_dump(mode="json")
        except Exception:
            return str(x)
    return str(x)


class HumanFeedbackCallback(Callback):
    """Dump per-row `(input, expected, predicted, run_id, agent_path)` tuples
    to an append-only NDJSON file so a human can rate them later.

    Row shape::

        {
          "id": str,                  # sha256(predicted_json)[:16]
          "run_id": str,
          "agent_path": str,
          "input": dict | str,        # model_dump(mode="json") or str(x)
          "expected": dict | str | None,
          "predicted": dict | str | None,
          "rating": None,             # human fills in later
          "rationale": None,
          "written_at": iso8601
        }

    ``on="val"`` (default) writes rows from each ``on_validation_end``
    report. ``on="train"`` wires in via a trainer hook that is not yet
    available; for now "train" falls through to no-op on
    ``on_batch_end`` (the Trainer doesn't expose predicted outputs to
    callbacks).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        on: Literal["train", "val"] = "val",
        agent_path: str = "",
    ) -> None:
        self.path = Path(path)
        self.on = on
        self.agent_path = agent_path
        self._rows_written: int = 0

    async def on_validation_end(
        self, trainer: "Trainer[Any, Any]", report: EvalReport
    ) -> None:
        if self.on != "val":
            return
        self._append_rows(report)

    def _append_rows(self, report: EvalReport) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        run_id = _RUN_ID.get() or ""
        now = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as f:
            for row in report.rows:
                predicted_obj = row.get("predicted")
                if predicted_obj is None:
                    continue
                row_id = _row_id(predicted_obj)
                out_row = {
                    "id": row_id,
                    "run_id": run_id,
                    "agent_path": self.agent_path,
                    "input": row.get("input"),
                    "expected": row.get("expected"),
                    "predicted": predicted_obj,
                    "rating": None,
                    "rationale": None,
                    "written_at": now,
                }
                f.write(json.dumps(out_row, sort_keys=True) + "\n")
                self._rows_written += 1


class Curriculum(Callback):
    """Re-order each epoch's data by per-sample gradient severity.

    After each epoch, reads ``trainer.last_epoch_per_sample_severity``
    (populated by ``Trainer._run_batch``) and calls ``set_order()`` on the
    loader's sampler so the next epoch sees examples in severity order.

    Modes:

    - ``"hard_first"`` — descending severity every epoch.
    - ``"easy_first"`` — ascending severity every epoch.
    - ``"anneal"`` — hard-first for the first ``warmup_epochs`` epochs,
      then random (matches the curriculum-learning literature and avoids
      overfitting to the difficulty order once the model has improved).

    Requires the loader's sampler to expose a ``set_order(indices)`` method.
    Use ``PermutableSampler`` from ``operad.data`` when constructing the
    ``DataLoader``; a ``UserWarning`` is emitted if the sampler lacks the
    hook. When combined with ``WeightedRandomSampler`` or
    ``StratifiedSampler``, Curriculum overrides their natural ordering —
    this is intentional but may surprise users, hence the ``on_fit_start``
    warning.
    """

    _OVERRIDE_SAMPLER_TYPES = ("WeightedRandomSampler", "StratifiedSampler")

    def __init__(
        self,
        monitor: str = "severity_per_sample",
        mode: Literal["hard_first", "easy_first", "anneal"] = "hard_first",
        warmup_epochs: int = 1,
    ) -> None:
        if mode not in ("hard_first", "easy_first", "anneal"):
            raise ValueError(
                f"mode must be 'hard_first', 'easy_first', or 'anneal', got {mode!r}"
            )
        if warmup_epochs < 0:
            raise ValueError("warmup_epochs must be non-negative")
        self.monitor = monitor
        self.mode = mode
        self.warmup_epochs = warmup_epochs
        self._epoch_count: int = 0

    async def on_fit_start(self, trainer: "Trainer[Any, Any]") -> None:
        self._epoch_count = 0
        sampler = getattr(getattr(trainer, "loader", None), "_sampler", None)
        if sampler is not None and type(sampler).__name__ in self._OVERRIDE_SAMPLER_TYPES:
            warnings.warn(
                f"Curriculum: loader uses {type(sampler).__name__}, whose natural "
                "ordering will be overridden by Curriculum.set_order().",
                UserWarning,
                stacklevel=2,
            )

    async def on_epoch_end(
        self, trainer: "Trainer[Any, Any]", report: EpochReport
    ) -> None:
        self._epoch_count += 1

        loader = getattr(trainer, "loader", None)
        sampler = getattr(loader, "_sampler", None)
        if sampler is None or not hasattr(sampler, "set_order"):
            warnings.warn(
                "Curriculum: loader.sampler does not support set_order(); "
                "wrap it in PermutableSampler (operad.data.PermutableSampler).",
                UserWarning,
                stacklevel=2,
            )
            return

        severity_map: dict[int, float] = trainer.last_epoch_per_sample_severity
        if not severity_map:
            return

        indices = list(severity_map.keys())

        if self.mode == "hard_first":
            ordered = sorted(indices, key=lambda i: severity_map[i], reverse=True)
        elif self.mode == "easy_first":
            ordered = sorted(indices, key=lambda i: severity_map[i])
        else:  # anneal
            if self._epoch_count <= self.warmup_epochs:
                ordered = sorted(indices, key=lambda i: severity_map[i], reverse=True)
            else:
                import random as _random
                ordered = indices[:]
                _random.shuffle(ordered)

        sampler.set_order(ordered)


__all__ = [
    "BestCheckpoint",
    "Callback",
    "Curriculum",
    "EarlyStopping",
    "EarlyStoppingSpec",
    "GradClip",
    "HumanFeedbackCallback",
    "LearningRateLogger",
    "MemoryRotation",
    "PromptDrift",
]
