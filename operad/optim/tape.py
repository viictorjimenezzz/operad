"""Forward-pass recording surface for `operad.optim`.

A `Tape` is an ordered record of every `Agent.invoke` that fired inside
an active `tape()` context, populated by installing a `TapeObserver`
on the runtime observer registry. Subsequent optimization waves walk
the tape in reverse (`backward()`, wave 3-1) to propagate textual
gradients through each node.

The tape relies entirely on existing runtime mechanics: it does not
touch `operad/runtime/observers/*` or `operad/core/agent.py`.
"""

from __future__ import annotations

import contextlib
import json
import uuid
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator

from pydantic import BaseModel

from operad.runtime.observers.base import (
    AgentEvent,
    Observer,
    _PATH_STACK,
    registry,
)

if TYPE_CHECKING:
    from operad.core.agent import Agent

# Stream 2-1 will expose a gradient-enabled flag via
# `operad.optim.context`. Until it lands, the fallback is "always
# record"; when it lands, `on_event` gates recording on the flag.
try:  # pragma: no cover - exercised once 2-1 merges
    from operad.optim.context import _GRAD_ENABLED  # type: ignore[import-not-found]
except ImportError:
    _GRAD_ENABLED = None  # type: ignore[assignment]


@dataclass(eq=False)
class TapeEntry:
    """One recorded `Agent.invoke` — inputs, outputs, timing, prompt."""

    run_id: str
    agent_path: str
    agent_ref: "weakref.ref[Agent[Any, Any]]"
    input: BaseModel
    output: BaseModel | None
    rendered_prompt: str | list[dict[str, str]] | None
    started_at: float
    finished_at: float | None
    event_id: str
    is_leaf: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(eq=False)
class Tape:
    """Ordered record of agent invocations within a single root run.

    `entries` is in invocation-start order (parent before children,
    siblings in the order their `start` events fired). Use
    `entries_in_reverse()` when walking the graph backward.
    """

    entries: list[TapeEntry] = field(default_factory=list)
    root_input: BaseModel | None = None
    root_output: BaseModel | None = None

    def entries_in_reverse(self) -> Iterator[TapeEntry]:
        return reversed(self.entries)

    def entry_for_path(self, path: str) -> TapeEntry | None:
        for entry in self.entries:
            if entry.agent_path == path:
                return entry
        return None

    def children_of(self, path: str) -> list[TapeEntry]:
        prefix = path + "."
        return [
            e for e in self.entries
            if e.agent_path.startswith(prefix)
            and "." not in e.agent_path[len(prefix):]
        ]

    def parents_of(self, path: str) -> list[TapeEntry]:
        out: list[TapeEntry] = []
        for entry in self.entries:
            p = entry.agent_path
            if p != path and path.startswith(p + "."):
                out.append(entry)
        return out

    def to_jsonl(self, path: Path | str) -> None:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            for entry in self.entries:
                record = {
                    "run_id": entry.run_id,
                    "agent_path": entry.agent_path,
                    "event_id": entry.event_id,
                    "is_leaf": entry.is_leaf,
                    "started_at": entry.started_at,
                    "finished_at": entry.finished_at,
                    "input": _dump(entry.input),
                    "output": _dump(entry.output),
                    "rendered_prompt": entry.rendered_prompt,
                    "metadata": entry.metadata,
                }
                fh.write(json.dumps(record) + "\n")


def _dump(model: BaseModel | None) -> Any:
    if model is None:
        return None
    return model.model_dump(mode="json")


class TapeObserver:
    """`Observer` that records each `Agent.invoke` into a `Tape`."""

    def __init__(self, tape: Tape, *, capture_prompts: bool = True) -> None:
        self._tape = tape
        self._capture_prompts = capture_prompts
        self._pending: dict[str, list[TapeEntry]] = {}
        self._root_path: str | None = None

    async def on_event(self, event: AgentEvent) -> None:
        if _GRAD_ENABLED is not None and _GRAD_ENABLED.get() is False:
            return
        if event.kind == "chunk":
            return

        stack = _PATH_STACK.get()
        if stack is None:
            # Defensive: observer fired outside an active invoke.
            return
        agent, _ = stack

        if event.kind == "start":
            self._on_start(event, agent)
        elif event.kind == "end":
            self._on_end(event, agent)
        elif event.kind == "error":
            self._on_error(event)

    def _on_start(self, event: AgentEvent, agent: "Agent[Any, Any]") -> None:
        if event.input is None:
            return
        entry = TapeEntry(
            run_id=event.run_id,
            agent_path=event.agent_path,
            agent_ref=weakref.ref(agent),
            input=event.input,
            output=None,
            rendered_prompt=None,
            started_at=event.started_at,
            finished_at=None,
            event_id=uuid.uuid4().hex,
            is_leaf=not bool(getattr(agent, "_children", {})),
            metadata=dict(event.metadata),
        )
        self._tape.entries.append(entry)
        self._pending.setdefault(event.agent_path, []).append(entry)
        if self._root_path is None:
            self._root_path = event.agent_path
            self._tape.root_input = event.input

    def _on_end(self, event: AgentEvent, agent: "Agent[Any, Any]") -> None:
        entry = self._pop_pending(event.agent_path)
        if entry is None:
            return
        entry.output = event.output
        entry.finished_at = event.finished_at
        if event.metadata:
            entry.metadata.update(event.metadata)
        if self._capture_prompts:
            entry.rendered_prompt = _safe_render_prompt(agent)
        if event.agent_path == self._root_path:
            self._tape.root_output = event.output

    def _on_error(self, event: AgentEvent) -> None:
        entry = self._pop_pending(event.agent_path)
        if entry is None:
            return
        try:
            self._tape.entries.remove(entry)
        except ValueError:
            pass

    def _pop_pending(self, path: str) -> TapeEntry | None:
        stack = self._pending.get(path)
        if not stack:
            return None
        entry = stack.pop()
        if not stack:
            del self._pending[path]
        return entry


def _safe_render_prompt(
    agent: "Agent[Any, Any]",
) -> str | list[dict[str, str]] | None:
    try:
        return agent.format_system_message()
    except Exception:
        return None


_ACTIVE_TAPE: TapeObserver | None = None


def enabled() -> bool:
    """Whether a `tape()` would record events right now.

    True when `operad.optim.context._GRAD_ENABLED` is unset (the 2-1
    fallback) or set to True; False when an active gradient-disabling
    context (e.g. `no_grad()`) has switched it off.
    """
    if _GRAD_ENABLED is None:
        return True
    return bool(_GRAD_ENABLED.get())


@contextlib.asynccontextmanager
async def tape(*, capture_prompts: bool = True) -> AsyncIterator[Tape]:
    """Record every `Agent.invoke` inside the context into a `Tape`.

    Nested `tape()` calls raise `RuntimeError`: a single root run per
    tape is the invariant that `backward()` relies on.
    """
    global _ACTIVE_TAPE
    if _ACTIVE_TAPE is not None:
        raise RuntimeError("tape() cannot be nested")
    t = Tape()
    observer: Observer = TapeObserver(t, capture_prompts=capture_prompts)
    _ACTIVE_TAPE = observer  # type: ignore[assignment]
    registry.register(observer)
    try:
        yield t
    finally:
        registry.unregister(observer)
        _ACTIVE_TAPE = None
