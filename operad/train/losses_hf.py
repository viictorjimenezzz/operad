"""`HumanFeedbackLoss` — score an agent against a human-rated NDJSON file.

Pairs with `operad.train.callbacks.HumanFeedbackCallback`, which writes
rows keyed by ``sha256(predicted_json)[:16]``. At training time, the
loss hashes each ``predicted`` the trainer hands it and looks up the
corresponding human rating (1-5). Unrated rows return a neutral score
of ``0.5`` with a null gradient, so the trainer still counts the
sample but applies no pressure — the agent effectively only gets
feedback on outputs the human has actually rated.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..metrics.base import MetricBase
from ..optim.parameter import TextualGradient
from .callbacks import _row_id


_NEUTRAL_SCORE = 0.5
_LOGGER = logging.getLogger("operad.train")


class HumanFeedbackLoss(MetricBase):
    """Lift human 1-5 ratings into a textual-gradient loss."""

    def __init__(
        self,
        ratings_path: str | Path,
        *,
        gradient_template: str = (
            "Human rated this output {rating}/5. Rationale: {rationale}"
        ),
        reload_per_epoch: bool = False,
        name: str = "human_feedback",
    ) -> None:
        self.ratings_path = Path(ratings_path)
        self.gradient_template = gradient_template
        self.reload_per_epoch = reload_per_epoch
        self.name = name
        self._by_id: dict[str, dict[str, Any]] | None = None
        self._mtime: float | None = None

    def reload(self) -> None:
        """Force cache invalidation; next _load() re-reads the file."""
        self._by_id = None
        self._mtime = None

    def _load(self) -> dict[str, dict[str, Any]]:
        current_mtime: float | None = None
        if self.ratings_path.exists():
            current_mtime = self.ratings_path.stat().st_mtime
        if (
            self._by_id is not None
            and not self.reload_per_epoch
            and current_mtime == self._mtime
        ):
            return self._by_id
        by_id: dict[str, dict[str, Any]] = {}
        if self.ratings_path.exists():
            for line in self.ratings_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    _LOGGER.warning("hf ratings: skipping malformed line: %r", line[:120])
                    continue
                row_id = row.get("id")
                if isinstance(row_id, str):
                    by_id[row_id] = row  # later entries overwrite earlier ones
        self._mtime = current_mtime
        self._by_id = by_id
        return by_id

    async def score(
        self, predicted: BaseModel, expected: BaseModel
    ) -> float:
        s, _ = await self.compute(predicted, expected)
        return s

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        del expected
        by_id = self._load()
        row_id = _row_id(predicted)
        row = by_id.get(row_id)
        rating = row.get("rating") if row is not None else None
        if not isinstance(rating, (int, float)):
            return _NEUTRAL_SCORE, TextualGradient.null_gradient()
        score_val = max(0.0, min(1.0, float(rating) / 5.0))
        rationale = str(row.get("rationale") or "")
        if score_val >= 1.0:
            return score_val, TextualGradient.null_gradient()
        msg = self.gradient_template.format(
            rating=rating, rationale=rationale or "(none)"
        )
        sev = max(0.0, min(1.0, 1.0 - score_val))
        return score_val, TextualGradient(message=msg, severity=sev)


__all__ = ["HumanFeedbackLoss"]
