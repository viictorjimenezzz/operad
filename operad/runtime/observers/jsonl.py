"""NDJSON observer: append one JSON object per event to a file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .base import AgentEvent


def _dump_payload(x: BaseModel | None) -> Any:
    if x is None:
        return None
    return x.model_dump(mode="json")


class JsonlObserver:
    """Append one line of JSON per event. Flushes after every write."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    async def on_event(self, event: AgentEvent) -> None:
        record: dict[str, Any] = {
            "run_id": event.run_id,
            "agent_path": event.agent_path,
            "kind": event.kind,
            "input": _dump_payload(event.input),
            "output": _dump_payload(event.output),
            "started_at": event.started_at,
            "finished_at": event.finished_at,
            "metadata": event.metadata,
        }
        if event.error is not None:
            record["error"] = {
                "type": type(event.error).__name__,
                "message": str(event.error),
            }
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
