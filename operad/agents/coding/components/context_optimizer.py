"""Fill a PRDiff's per-chunk context from a caller-supplied reader."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ....core.agent import Agent
from ..types import DiffChunk, PRDiff

ReadFile = Callable[[str], Awaitable[str]]


class ContextOptimizer(Agent[PRDiff, PRDiff]):
    """Populate ``DiffChunk.context`` for every chunk in the PR.

    Custom-forward leaf: it does not talk to a model, so it does not
    need a ``Configuration``. Iterating ``x.chunks`` inside ``forward``
    is safe because leaves are not symbolically traced — the build
    pipeline short-circuits leaf invocations.
    """

    input = PRDiff
    output = PRDiff

    role = "Fills chunk-level surrounding-code context from disk."
    task = "Read each chunk's file and attach a minimal surrounding snippet."
    rules = ("Do not modify old/new hunk bodies.",)

    def __init__(self, *, read_file: ReadFile, window: int = 40) -> None:
        super().__init__(config=None, input=PRDiff, output=PRDiff)
        self._read_file = read_file
        self._window = window

    async def forward(self, x: PRDiff) -> PRDiff:  # type: ignore[override]
        enriched: list[DiffChunk] = []
        for c in x.chunks:
            if c.context or not c.path:
                enriched.append(c)
                continue
            try:
                body = await self._read_file(c.path)
            except Exception:
                enriched.append(c)
                continue
            enriched.append(c.model_copy(update={"context": _trim(body, self._window)}))
        return PRDiff(chunks=enriched)


def _trim(body: str, window: int) -> str:
    lines = body.splitlines()
    if len(lines) <= window * 2:
        return body
    return "\n".join(lines[:window] + ["..."] + lines[-window:])
