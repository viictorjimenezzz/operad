from __future__ import annotations

"""Owner: 1-5-trace-feedback-models.

Human feedback schema and JSON helpers.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class HumanFeedback(BaseModel):
    """The user's natural-language critique of a final answer."""

    trace_id: str
    final_answer_critique: str
    target_path: str | None = None
    severity: float = 1.0
    desired_behavior: str | None = None

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_json(cls, path: Path) -> "HumanFeedback":
        """Read feedback from a JSON file."""

        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def to_json(self, path: Path) -> None:
        """Write feedback to a deterministic JSON file."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                self.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def template(cls, trace_id: str) -> "HumanFeedback":
        """Return a default-filled feedback template for an editor."""

        return cls(trace_id=trace_id, final_answer_critique="")


__all__ = ["HumanFeedback"]
