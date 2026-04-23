"""Streaming primitives: `ChunkEvent` yielded by `Agent.stream(x)`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkEvent:
    """One mid-run token piece surfaced by `Agent.stream(x)`."""

    text: str
    index: int
    agent_path: str
    run_id: str
