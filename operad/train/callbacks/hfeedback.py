"""Human-feedback row writer callback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ...benchmark.evaluate import EvalReport
from ...optim.losses.hfeedback import _row_id
from ...runtime.observers.base import _RUN_ID
from .callback import Callback

if TYPE_CHECKING:
    from ..trainer import Trainer


class HumanFeedbackCallback(Callback):
    """Append validation rows to an NDJSON file for human rating."""

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
                out_row = {
                    "id": _row_id(predicted_obj),
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


__all__ = ["HumanFeedbackCallback"]
