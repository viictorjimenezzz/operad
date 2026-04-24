"""`TrainerProgressObserver` — Rich nested progress bars for `Trainer.fit`.

Listens for the `algo_start` / `iteration` / `algo_end` events that
`Trainer.fit` emits (plus `batch_start` / `batch_end` from `DataLoader`)
and renders two nested Rich progress bars: outer by epoch, inner by
batch within the current epoch. Also exposes a plain-state dict on
`observer.state` so tests can assert without needing `rich` installed.

Install the optional ``rich`` extra to see bars:

    uv pip install 'operad[observers]'

Without Rich, the observer still tracks state but does not draw
anything.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ..runtime.events import AlgorithmEvent
from ..runtime.observers.base import Event


@dataclass
class _ProgressState:
    run_id: str | None = None
    epochs_total: int | None = None
    current_epoch: int = 0
    batches_total: int | None = None
    current_batch: int = 0
    started_at: float | None = None
    last_batch_at: float | None = None
    rate_batches_per_s: float = 0.0
    finished: bool = False
    rate_ema_alpha: float = 0.3

    # Per-epoch batch counters — used to infer total batches on subsequent
    # epochs, since the DataLoader doesn't know its length up-front.
    _this_epoch_batches: int = 0
    _prev_epoch_batches: int | None = None
    _last_batch_duration_s: float = 0.0


class TrainerProgressObserver:
    """Operad observer that renders a Rich progress bar for `Trainer.fit`.

    Usage::

        from operad.runtime.observers import registry
        from operad.train import TrainerProgressObserver

        registry.register(TrainerProgressObserver())

    The observer is idempotent across training runs: calling ``reset``
    (or the next ``algo_start`` from a `Trainer`) discards the prior
    bar and starts fresh.
    """

    def __init__(self, *, transient: bool = False) -> None:
        self.state = _ProgressState()
        self.transient = transient
        self._progress = None
        self._epoch_task_id = None
        self._batch_task_id = None
        try:  # rich is optional; observer no-ops without it.
            import rich  # noqa: F401
            self._rich_available = True
        except ImportError:
            self._rich_available = False

    # --- public API ----------------------------------------------------------

    def reset(self) -> None:
        self._stop_bars()
        self.state = _ProgressState()

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent):
            return
        path = event.algorithm_path
        kind = event.kind
        payload = event.payload or {}

        if path == "Trainer" and kind == "algo_start":
            self._on_trainer_start(event, payload)
        elif path == "Trainer" and kind == "iteration":
            self._on_trainer_iteration(payload)
        elif path == "Trainer" and kind in ("algo_end", "algo_error"):
            self._on_trainer_end()
        elif path == "DataLoader" and kind == "batch_start":
            self._on_batch_start(payload)
        elif path == "DataLoader" and kind == "batch_end":
            self._on_batch_end(payload)

    # --- handlers ------------------------------------------------------------

    def _on_trainer_start(
        self, event: AlgorithmEvent, payload: dict[str, Any]
    ) -> None:
        self.reset()
        epochs = payload.get("epochs")
        self.state.run_id = event.run_id
        self.state.epochs_total = int(epochs) if isinstance(epochs, int) else None
        self.state.started_at = event.started_at or time.monotonic()
        self._start_bars()

    def _on_trainer_iteration(self, payload: dict[str, Any]) -> None:
        phase = payload.get("phase")
        epoch = payload.get("epoch")
        if phase == "epoch_start" and isinstance(epoch, int):
            self.state.current_epoch = epoch
            # Roll over batch counters.
            if self.state._this_epoch_batches > 0:
                self.state._prev_epoch_batches = self.state._this_epoch_batches
            self.state._this_epoch_batches = 0
            self.state.current_batch = 0
            # Infer batches_total from the first completed epoch once known.
            if self.state.batches_total is None and self.state._prev_epoch_batches:
                self.state.batches_total = self.state._prev_epoch_batches
            self._update_epoch_bar()
        elif phase == "epoch_end":
            # At end of epoch 0 we finally know batches_total.
            if self.state.batches_total is None:
                self.state.batches_total = self.state._this_epoch_batches

    def _on_trainer_end(self) -> None:
        self.state.finished = True
        self._finalise_bars()

    def _on_batch_start(self, payload: dict[str, Any]) -> None:
        idx = payload.get("batch_index")
        if isinstance(idx, int):
            self.state.current_batch = idx + 1  # 1-indexed for display
        self.state._this_epoch_batches = self.state.current_batch
        self.state.last_batch_at = time.monotonic()
        self._update_batch_bar()

    def _on_batch_end(self, payload: dict[str, Any]) -> None:
        duration_ms = payload.get("duration_ms")
        if isinstance(duration_ms, (int, float)) and duration_ms > 0:
            seconds = float(duration_ms) / 1000.0
            self.state._last_batch_duration_s = seconds
            sample_rate = 1.0 / max(seconds, 1e-6)
            if self.state.rate_batches_per_s <= 0:
                self.state.rate_batches_per_s = sample_rate
            else:
                alpha = self.state.rate_ema_alpha
                self.state.rate_batches_per_s = (
                    alpha * sample_rate + (1 - alpha) * self.state.rate_batches_per_s
                )

    # --- Rich bar plumbing ---------------------------------------------------

    def _start_bars(self) -> None:
        if not self._rich_available:
            return
        try:
            from rich.progress import (
                BarColumn,
                MofNCompleteColumn,
                Progress,
                TextColumn,
                TimeRemainingColumn,
            )
            self._progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
                transient=self.transient,
            )
            self._progress.start()
            self._epoch_task_id = self._progress.add_task(
                "epochs",
                total=self.state.epochs_total or 1,
                completed=0,
            )
            self._batch_task_id = self._progress.add_task(
                "batches",
                total=self.state.batches_total or 1,
                completed=0,
            )
        except Exception:  # pragma: no cover — defensive; never block fit()
            self._progress = None

    def _update_epoch_bar(self) -> None:
        if self._progress is None or self._epoch_task_id is None:
            return
        self._progress.update(
            self._epoch_task_id, completed=self.state.current_epoch
        )
        if self.state.batches_total and self._batch_task_id is not None:
            self._progress.update(
                self._batch_task_id, total=self.state.batches_total, completed=0
            )

    def _update_batch_bar(self) -> None:
        if self._progress is None or self._batch_task_id is None:
            return
        total = self.state.batches_total or max(self.state.current_batch, 1)
        self._progress.update(
            self._batch_task_id,
            total=total,
            completed=self.state.current_batch,
        )

    def _finalise_bars(self) -> None:
        if self._progress is None:
            return
        if self._epoch_task_id is not None and self.state.epochs_total:
            self._progress.update(
                self._epoch_task_id, completed=self.state.epochs_total
            )
        if self._batch_task_id is not None and self.state.batches_total:
            self._progress.update(
                self._batch_task_id, completed=self.state.batches_total
            )
        self._stop_bars()

    def _stop_bars(self) -> None:
        if self._progress is None:
            return
        try:
            self._progress.stop()
        except Exception:  # pragma: no cover
            pass
        self._progress = None
        self._epoch_task_id = None
        self._batch_task_id = None


__all__ = ["TrainerProgressObserver"]
