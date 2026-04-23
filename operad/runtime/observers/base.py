"""Observer protocol, event shape, registry, and runtime context vars."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from ...core.agent import Agent


@dataclass
class AgentEvent:
    run_id: str
    agent_path: str
    kind: Literal["start", "end", "error"]
    input: BaseModel | None
    output: BaseModel | None
    error: BaseException | None
    started_at: float
    finished_at: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Observer(Protocol):
    async def on_event(self, event: AgentEvent) -> None: ...


class ObserverRegistry:
    def __init__(self) -> None:
        self._observers: list[Observer] = []

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

    async def notify(self, event: AgentEvent) -> None:
        for observer in list(self._observers):
            try:
                await observer.on_event(event)
            except Exception:
                # Observer failures must never break the pipeline.
                pass


registry = ObserverRegistry()


# Root-run correlation: preserved across a whole invocation tree.
_RUN_ID: ContextVar[str | None] = ContextVar("_RUN_ID", default=None)

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
