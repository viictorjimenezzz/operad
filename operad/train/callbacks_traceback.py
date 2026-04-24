"""`TracebackOnFailure` — opt-in `Callback` that logs a `PromptTraceback`
when a training batch's loss exceeds a threshold.

The callback is best-effort: today's `Trainer` keeps only
`_last_batch_tape_entries` (a count), so the callback probes the trainer
for `_last_tape` and `_last_loss_grad` and no-ops if they are absent. A
future Trainer change can surface those attributes to make this callback
light up without further modification.

Lives in a sibling file (rather than `operad/train/callbacks.py`) to keep
the 5-4 PR conflict-free with concurrent wave-5-3 edits to `callbacks.py`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from operad.optim.traceback import PromptTraceback
from operad.train.callbacks import Callback

if TYPE_CHECKING:
    from operad.data.loader import Batch
    from operad.train.trainer import Trainer


class TracebackOnFailure(Callback):
    """Construct and log a `PromptTraceback` when ``loss > loss_threshold``.

    ``save_dir`` — if set, each triggered traceback is also dumped as an
    NDJSON file named ``step-<step>.ndjson``.
    """

    def __init__(
        self,
        loss_threshold: float,
        *,
        save_dir: Path | str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._loss_threshold = loss_threshold
        self._save_dir: Path | None = Path(save_dir) if save_dir is not None else None
        self._logger = logger or logging.getLogger("operad.train")

    async def on_batch_end(
        self,
        trainer: "Trainer[Any, Any]",
        batch: "Batch[Any, Any]",
        step: int,
        loss: float,
    ) -> None:
        if loss <= self._loss_threshold:
            return

        tape = getattr(trainer, "_last_tape", None)
        last_grad = getattr(trainer, "_last_loss_grad", None)
        if tape is None or last_grad is None:
            self._logger.debug(
                "TracebackOnFailure: trainer does not expose `_last_tape` / "
                "`_last_loss_grad`; skipping (step=%d, loss=%.3f)",
                step,
                loss,
            )
            return

        tb = PromptTraceback.from_run(tape, last_grad)
        self._logger.warning(
            "Prompt traceback at step %d (loss=%.3f):\n%s", step, loss, tb
        )
        if self._save_dir is not None:
            self._save_dir.mkdir(parents=True, exist_ok=True)
            tb.save(self._save_dir / f"step-{step:05d}.ndjson")
