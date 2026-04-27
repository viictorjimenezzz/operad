"""Prompt-drift callback."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from ...runtime.observers.base import emit_algorithm_event
from ..report import EpochReport
from .callback import Callback

if TYPE_CHECKING:
    from ..trainer import Trainer


class PromptDrift(Callback):
    """Warn when ``agent.hash_content`` changes too many times in a fit."""

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


__all__ = ["PromptDrift"]
