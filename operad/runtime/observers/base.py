"""Observer protocol, event shape, registry, and runtime context vars."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator, Literal, Protocol, runtime_checkable
from uuid import uuid4

_log = logging.getLogger("operad.observers")

from pydantic import BaseModel

from ..events import AlgorithmEvent, AlgoKind

if TYPE_CHECKING:
    from ...core.agent import Agent


@dataclass
class AgentEvent:
    run_id: str
    agent_path: str
    kind: Literal["start", "end", "error", "chunk"]
    input: BaseModel | None
    output: BaseModel | None
    error: BaseException | None
    started_at: float
    finished_at: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


Event = AgentEvent | AlgorithmEvent


@runtime_checkable
class Observer(Protocol):
    async def on_event(self, event: Event) -> None: ...


class ObserverRegistry:
    def __init__(self, strict: bool = False) -> None:
        self._observers: list[Observer] = []
        self._errors: dict[int, int] = {}
        self._warned: set[int] = set()
        self._strict: bool = strict or os.environ.get("OPERAD_OBSERVER_STRICT", "") not in ("", "0", "false")

    def register(self, observer: Observer) -> None:
        self._observers.append(observer)

    def unregister(self, observer: Observer) -> None:
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    def clear(self) -> None:
        self._observers.clear()

    def __len__(self) -> int:
        return len(self._observers)

    def errors(self) -> dict[int, int]:
        return dict(self._errors)

    async def notify(self, event: Event) -> None:
        if _MUTE_NOTIFICATIONS.get():
            return
        for observer in list(self._observers):
            try:
                await observer.on_event(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                oid = id(observer)
                self._errors[oid] = self._errors.get(oid, 0) + 1
                if oid not in self._warned:
                    self._warned.add(oid)
                    _log.warning("Observer %r raised on first failure", observer, exc_info=True)
                else:
                    _log.debug("Observer %r raised again", observer, exc_info=True)
                if self._strict:
                    raise


registry = ObserverRegistry()


# Root-run correlation: preserved across a whole invocation tree.
_RUN_ID: ContextVar[str | None] = ContextVar("_RUN_ID", default=None)

# Per-invocation correlation id. Distinguishes concurrent invocations
# that share `(run_id, agent_path)`.
_INVOKE_ID: ContextVar[str | None] = ContextVar("_INVOKE_ID", default=None)

# Current parent (agent, dotted_path) so children can compute their path.
_PATH_STACK: ContextVar[tuple["Agent[Any, Any]", str] | None] = ContextVar(
    "_PATH_STACK", default=None
)

# Per-invoke scratch dict for retry metadata. `Agent.invoke` sets it
# before dispatching to `forward` and merges it into the terminal event
# metadata; the default leaf forward populates it via `with_retry`'s
# on_attempt callback.
_RETRY_META: ContextVar[dict[str, Any] | None] = ContextVar(
    "_RETRY_META", default=None
)

# Task-local guard used by dashboard experiments so cloned-agent invocations
# do not leak synthetic events into live observer streams.
_MUTE_NOTIFICATIONS: ContextVar[bool] = ContextVar(
    "_MUTE_NOTIFICATIONS", default=False
)

# Algorithm-scoped run id. Set by _enter_algorithm_run() so nested
# AgentEvents can carry parent_run_id in metadata.
_ALGO_RUN_ID: ContextVar[str | None] = ContextVar("_ALGO_RUN_ID", default=None)


@contextmanager
def _enter_algorithm_run(rid: str | None = None) -> Iterator[str]:
    """Reuse the enclosing run_id if one is set; otherwise mint or adopt
    one for the duration of the scope so nested `AgentEvent`s share it.

    When a new run_id is minted (or `rid` is adopted), `_ALGO_RUN_ID`
    is also set to that id so that nested `AgentEvent` metadata can
    carry `parent_run_id`. `rid` lets a long-lived caller (e.g. an
    `Optimizer.session()`) pin a stable id across multiple entries.
    """
    existing = _RUN_ID.get()
    if existing is not None:
        yield existing
        return
    rid = rid or uuid4().hex
    tok_r = _RUN_ID.set(rid)
    tok_a = _ALGO_RUN_ID.set(rid)
    try:
        yield rid
    finally:
        _RUN_ID.reset(tok_r)
        _ALGO_RUN_ID.reset(tok_a)


@contextmanager
def suppress_notifications() -> Iterator[None]:
    tok = _MUTE_NOTIFICATIONS.set(True)
    try:
        yield
    finally:
        _MUTE_NOTIFICATIONS.reset(tok)


async def emit_algorithm_event(
    kind: AlgoKind,
    *,
    algorithm_path: str,
    payload: dict[str, Any],
    started_at: float | None = None,
    finished_at: float | None = None,
) -> None:
    """Fire one `AlgorithmEvent` on the global registry using the current run_id.

    The caller must run inside `_enter_algorithm_run()` so a run_id exists.
    """
    now = time.time()
    await registry.notify(
        AlgorithmEvent(
            run_id=_RUN_ID.get() or "",
            algorithm_path=algorithm_path,
            kind=kind,
            payload=payload,
            started_at=started_at if started_at is not None else now,
            finished_at=finished_at,
        )
    )
