"""The `build()` step: symbolic trace + type checks + graph capture.

`build_agent(root)` prepares an `Agent` for `invoke`-ability:

1. Validates that every agent in the tree has a usable typed contract.
2. Wires `strands.Agent.__init__` for leaf agents that rely on the default
   `forward` (ones whose `forward` is `Agent.forward` unchanged), threading
   the full `Configuration` through `operad.models.resolve_model`. The
   system prompt is rendered via `agent.format_system_message()`.
3. Runs a symbolic trace of the architecture with a sentinel input. Child
   invocations are intercepted by a `Tracer` installed via a `ContextVar`;
   each edge is type-checked and recorded. No LLM is contacted.
4. Stores the resulting `AgentGraph` on `root._graph` and flips `_built=True`
   on every agent in the tree.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

import strands

from ..models import resolve_model
from ..utils.errors import BuildError
from .agent import Agent, _TRACER

NodeKind = Literal["leaf", "composite"]


@dataclass
class Node:
    """A traced agent node. Leaves have no outgoing edges in `AgentGraph`."""

    path: str
    input_type: type
    output_type: type
    kind: NodeKind


@dataclass
class Edge:
    """One recorded invocation: parent -> child, with the agreed types."""

    caller: str
    callee: str
    input_type: type
    output_type: type


@dataclass
class AgentGraph:
    """The computation graph captured at `build()` time."""

    root: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


def _node_kind(a: Agent[Any, Any]) -> NodeKind:
    return "composite" if a._children else "leaf"


def _is_default_forward(a: Agent[Any, Any]) -> bool:
    """True iff the agent will delegate to `strands.Agent.invoke_async`."""
    return type(a).forward is Agent.forward


class Tracer:
    """Intercepts sub-agent `invoke` calls during symbolic tracing."""

    def __init__(self, root: Agent[Any, Any]) -> None:
        self.root = root
        root_name = type(root).__name__
        self.graph = AgentGraph(
            root=root_name,
            nodes=[
                Node(
                    path=root_name,
                    input_type=root.input,  # type: ignore[arg-type]
                    output_type=root.output,  # type: ignore[arg-type]
                    kind=_node_kind(root),
                )
            ],
        )
        self._stack: list[tuple[Agent[Any, Any], str]] = []

    async def record(self, child: Agent[Any, Any], x: Any) -> Any:
        if not self._stack:
            parent_agent: Agent[Any, Any] = self.root
            parent_name = type(self.root).__name__
        else:
            parent_agent, parent_name = self._stack[-1]

        attr = _find_attr_name(parent_agent, child) or type(child).__name__
        callee = f"{parent_name}.{attr}"

        if child.input is None or child.output is None:
            raise BuildError(
                "prompt_incomplete", "missing input/output type", agent=callee
            )
        if not isinstance(x, child.input):
            raise BuildError(
                "input_mismatch",
                f"expected {child.input.__name__}, got {type(x).__name__}",
                agent=callee,
            )

        self.graph.nodes.append(
            Node(
                path=callee,
                input_type=child.input,
                output_type=child.output,
                kind=_node_kind(child),
            )
        )
        self.graph.edges.append(
            Edge(
                caller=parent_name,
                callee=callee,
                input_type=child.input,
                output_type=child.output,
            )
        )

        if child._children:
            self._stack.append((child, callee))
            try:
                sentinel = child.input.model_construct()
                out = await child.forward(sentinel)
                if not isinstance(out, child.output):
                    raise BuildError(
                        "output_mismatch",
                        f"forward returned {type(out).__name__}, "
                        f"expected {child.output.__name__}",
                        agent=callee,
                    )
            finally:
                self._stack.pop()

        return child.output.model_construct()


def _find_attr_name(parent: Agent[Any, Any], child: Agent[Any, Any]) -> str | None:
    for name, value in parent._children.items():
        if value is child:
            return name
    return None


def _walk(root: Agent[Any, Any]) -> Iterator[Agent[Any, Any]]:
    """Yield every descendant of `root` (breadth-first, de-duplicated)."""
    queue = list(root._children.values())
    seen: set[int] = set()
    while queue:
        a = queue.pop(0)
        if id(a) in seen:
            continue
        seen.add(id(a))
        yield a
        queue.extend(a._children.values())


def _tree(root: Agent[Any, Any]) -> Iterator[Agent[Any, Any]]:
    """Yield `root` followed by every descendant."""
    yield root
    yield from _walk(root)


def _validate(a: Agent[Any, Any]) -> None:
    """Ensure every agent in the tree has a usable contract.

    Composites (agents that override `forward`) may omit `config` because
    they never talk to a model; leaves require it.
    """
    if a.input is None or a.output is None:
        raise BuildError(
            "prompt_incomplete", "missing input/output type", agent=type(a).__name__
        )
    if _is_default_forward(a) and a.config is None:
        raise BuildError(
            "prompt_incomplete",
            "leaf agent requires `config`; pass one to the constructor",
            agent=type(a).__name__,
        )


def _init_strands(a: Agent[Any, Any]) -> None:
    """Initialize the strands.Agent half for default-forward leaves only.

    Composites (agents that override ``forward``) don't need strands
    wiring; they route calls to their children and never invoke the model
    themselves.
    """
    if not _is_default_forward(a):
        return
    try:
        from strands.types.agent import ConcurrentInvocationMode

        model = resolve_model(a.config)  # type: ignore[arg-type]
        system_prompt = a.format_system_message() or None
        strands.Agent.__init__(
            a,
            model=model,
            system_prompt=system_prompt,
            concurrent_invocation_mode=ConcurrentInvocationMode.UNSAFE_REENTRANT,
        )
    except BuildError:
        raise
    except Exception as e:
        raise BuildError(
            "trace_failed",
            f"strands.Agent init failed: {e}",
            agent=type(a).__name__,
        ) from e


async def _trace(root: Agent[Any, Any], tracer: Tracer) -> Any:
    token = _TRACER.set(tracer)
    try:
        sentinel = root.input.model_construct()  # type: ignore[union-attr]
        return await root.forward(sentinel)
    finally:
        _TRACER.reset(token)


async def abuild_agent(root: Agent[Any, Any]) -> Agent[Any, Any]:
    """Compile an agent architecture (async entry point)."""
    for a in _tree(root):
        _validate(a)
    for a in _tree(root):
        _init_strands(a)

    tracer = Tracer(root)
    try:
        out = await _trace(root, tracer)
    except BuildError:
        raise
    except Exception as e:
        raise BuildError(
            "trace_failed", str(e), agent=type(root).__name__
        ) from e

    if not isinstance(out, root.output):  # type: ignore[arg-type]
        raise BuildError(
            "output_mismatch",
            f"{type(root).__name__}.forward returned {type(out).__name__}, "
            f"expected {root.output.__name__}",  # type: ignore[union-attr]
            agent=type(root).__name__,
        )

    object.__setattr__(root, "_graph", tracer.graph)
    object.__setattr__(root, "_built", True)
    for a in _walk(root):
        object.__setattr__(a, "_built", True)
    return root


def build_agent(root: Agent[Any, Any]) -> Agent[Any, Any]:
    """Compile an agent architecture (sync entry point).

    Raises `RuntimeError` if called from inside a running event loop; use
    `abuild_agent` (or `Agent.abuild()`) there instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(abuild_agent(root))
    raise RuntimeError(
        "build() cannot be called from a running event loop; "
        "use `await agent.abuild()` (or `await abuild_agent(agent)`) instead"
    )
