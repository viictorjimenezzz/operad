"""The `build()` step: symbolic trace + type checks + graph capture.

`build_agent(root)` prepares an `Agent` for `invoke`-ability:

1. Validates that every agent in the tree has a usable typed contract.
2. Constructs a `StrandsRunner` for leaf agents that rely on the default
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
import os
import traceback
import warnings
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, NoReturn

from pydantic import BaseModel

from .models import resolve_model
from ._strands_runner import StrandsRunner
from ..utils.errors import BuildError
from .agent import Agent, _TRACER

NodeKind = Literal["leaf", "composite"]

_CORE_DIR = os.path.dirname(os.path.abspath(__file__))


class _PayloadBranchAccess(Exception):
    """Internal signal — raised when a composite's `forward` reads a sentinel
    field during trace. Converted to `BuildError("payload_branch", ...)` at
    the nearest forward-call boundary.
    """

    def __init__(self, cls_name: str, field_name: str) -> None:
        self.cls_name = cls_name
        self.field_name = field_name


class _PayloadBranchDunder(Exception):
    """Internal signal — raised when a composite's `forward` exercises a
    branching dunder (`__bool__`, `__eq__`, `__iter__`, ...) on the
    sentinel during trace. Converted to `BuildError("payload_branch", ...)`
    at the nearest forward-call boundary.
    """

    def __init__(self, cls_name: str, dunder: str) -> None:
        self.cls_name = cls_name
        self.dunder = dunder


def _make_sentinel(cls: type[BaseModel]) -> BaseModel:
    """Return a trace-time sentinel of `cls` that raises on field reads
    and on value-branching dunders.

    The sentinel is an instance of a dynamic subclass of `cls`, so
    `isinstance(sentinel, cls)` still holds. Reads of any declared model
    field raise `_PayloadBranchAccess`; truthy/comparison/iteration
    dunders raise `_PayloadBranchDunder`. Pydantic internals and
    structural attribute access (`__class__`, `__repr__`, ...) pass
    through unchanged.
    """
    field_names = frozenset(cls.model_fields)
    cls_name = cls.__name__

    def _dunder(name: str) -> Any:
        def _trap(self: Any, *args: Any, **kwargs: Any) -> Any:
            raise _PayloadBranchDunder(cls_name, name)

        _trap.__name__ = name
        return _trap

    class _Sentinel(cls):  # type: ignore[misc, valid-type]
        def __getattribute__(self, name: str) -> Any:
            if name in field_names:
                raise _PayloadBranchAccess(cls_name, name)
            return object.__getattribute__(self, name)

        __bool__ = _dunder("__bool__")
        __eq__ = _dunder("__eq__")
        __ne__ = _dunder("__ne__")
        __lt__ = _dunder("__lt__")
        __le__ = _dunder("__le__")
        __gt__ = _dunder("__gt__")
        __ge__ = _dunder("__ge__")
        __hash__ = _dunder("__hash__")  # type: ignore[assignment]
        __iter__ = _dunder("__iter__")
        __len__ = _dunder("__len__")
        __contains__ = _dunder("__contains__")
        __getitem__ = _dunder("__getitem__")

    _Sentinel.__name__ = f"_Sentinel[{cls.__name__}]"
    _Sentinel.__qualname__ = _Sentinel.__name__
    return _Sentinel.model_construct()


def _user_frame(exc: BaseException) -> tuple[str, int] | None:
    """Walk `exc.__traceback__` from innermost outward; return the first
    frame whose filename is not inside `operad/core/` or `pydantic`.

    Returns ``(basename, lineno)`` or ``None`` if no such frame exists
    (e.g. forward was defined in a Jupyter cell or `exec`'d string).
    """
    try:
        frames = traceback.extract_tb(exc.__traceback__)
    except Exception:
        return None
    for frame in reversed(frames):
        fn = frame.filename or ""
        if not fn or fn.startswith("<"):
            continue
        try:
            abs_fn = os.path.abspath(fn)
        except Exception:
            continue
        if abs_fn.startswith(_CORE_DIR):
            continue
        if f"{os.sep}pydantic{os.sep}" in abs_fn:
            continue
        return (os.path.basename(fn), frame.lineno)
    return None


def _raise_payload_branch(
    exc: _PayloadBranchAccess | _PayloadBranchDunder,
    *,
    agent_name: str,
    composite_cls: str,
    io: tuple[type, type],
) -> NoReturn:
    """Convert a payload-branch signal into a `BuildError("payload_branch")`.

    Both `_PayloadBranchAccess` (field read) and `_PayloadBranchDunder`
    (truthy/comparison/iter) funnel through here so the two catch sites
    in ``_trace`` and ``Tracer.record`` stay tiny.
    """
    from .graph import to_mermaid_node

    if isinstance(exc, _PayloadBranchAccess):
        access = f"{exc.cls_name}.{exc.field_name!r}"
        note = f"read {exc.cls_name}.{exc.field_name} during trace"
    else:
        access = f"{exc.cls_name} via {exc.dunder}"
        note = f"{exc.cls_name} {exc.dunder} during trace"

    frame = _user_frame(exc)
    locus = f" at {frame[0]}:{frame[1]}" if frame else ""

    raise BuildError(
        "payload_branch",
        f"composite {composite_cls}.forward read "
        f"{access}{locus} during trace; "
        "route on a child's typed output (e.g. Router over a "
        "Literal choice) instead of the payload value",
        agent=agent_name,
        mermaid=to_mermaid_node(agent_name, io, note=note),
    ) from exc


@dataclass
class Node:
    """A traced agent node. Leaves have no outgoing edges in `AgentGraph`."""

    path: str
    input_type: type
    output_type: type
    kind: NodeKind
    class_name: str | None = None


@dataclass
class Edge:
    """One recorded invocation: parent -> child, with the agreed types."""

    caller: str
    callee: str
    input_type: type
    output_type: type
    class_name: str | None = None


@dataclass
class AgentGraph:
    """The computation graph captured at `build()` time."""

    root: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def _repr_html_(self) -> str:
        """Render the graph as a `<pre class="mermaid">` block.

        Compatible with JupyterLab's Mermaid extension, VS Code's
        built-in Mermaid preview, and marimo. No outbound network
        request — the Mermaid source is embedded verbatim and left for
        a front-end renderer to transform.
        """
        import html as _html

        from .graph import to_mermaid

        return f'<pre class="mermaid">{_html.escape(to_mermaid(self))}</pre>'


def _node_kind(a: Agent[Any, Any]) -> NodeKind:
    return "composite" if a._children else "leaf"


def _is_default_forward(a: Agent[Any, Any]) -> bool:
    """True iff the agent will delegate to its `StrandsRunner`."""
    return type(a).forward is Agent.forward


class Tracer:
    """Intercepts sub-agent `invoke` calls during symbolic tracing."""

    def __init__(self, root: Agent[Any, Any]) -> None:
        self.root = root
        root_name = root.name
        self.graph = AgentGraph(
            root=root_name,
            nodes=[
                Node(
                    path=root_name,
                    input_type=root.input,  # type: ignore[arg-type]
                    output_type=root.output,  # type: ignore[arg-type]
                    kind=_node_kind(root),
                    class_name=type(root).__name__,
                )
            ],
        )
        self._stack: list[tuple[Agent[Any, Any], str]] = []

    async def record(self, child: Agent[Any, Any], x: Any) -> Any:
        if not self._stack:
            parent_agent: Agent[Any, Any] = self.root
            parent_name = self.root.name
        else:
            parent_agent, parent_name = self._stack[-1]

        attr = _find_attr_name(parent_agent, child) or child.name
        callee = f"{parent_name}.{attr}"

        if child.input is None or child.output is None:
            raise BuildError(
                "prompt_incomplete", "missing input/output type", agent=callee
            )
        if not isinstance(x, child.input):
            from .graph import to_mermaid_edge

            caller_io = (
                (parent_agent.input, parent_agent.output)
                if parent_agent.input is not None
                and parent_agent.output is not None
                else None
            )
            raise BuildError(
                "input_mismatch",
                f"expected {child.input.__name__}, got {type(x).__name__}",
                agent=callee,
                mermaid=to_mermaid_edge(
                    parent_name,
                    callee,
                    (child.input, child.output),
                    caller_io=caller_io,
                    note=(
                        f"got {type(x).__name__}, "
                        f"expected {child.input.__name__}"
                    ),
                ),
            )

        self.graph.nodes.append(
            Node(
                path=callee,
                input_type=child.input,
                output_type=child.output,
                kind=_node_kind(child),
                class_name=type(child).__name__,
            )
        )
        self.graph.edges.append(
            Edge(
                caller=parent_name,
                callee=callee,
                input_type=child.input,
                output_type=child.output,
                class_name=type(child).__name__,
            )
        )

        if child._children:
            edges_before = len(self.graph.edges)
            self._stack.append((child, callee))
            try:
                sentinel = _make_sentinel(child.input)
                try:
                    out = await child.forward(sentinel)
                except (_PayloadBranchAccess, _PayloadBranchDunder) as exc:
                    _raise_payload_branch(
                        exc,
                        agent_name=callee,
                        composite_cls=type(child).__name__,
                        io=(child.input, child.output),
                    )
                if not isinstance(out, child.output):
                    from .graph import to_mermaid_node

                    raise BuildError(
                        "output_mismatch",
                        f"forward returned {type(out).__name__}, "
                        f"expected {child.output.__name__}",
                        agent=callee,
                        mermaid=to_mermaid_node(
                            callee,
                            (child.input, child.output),
                            note=(
                                f"returned {type(out).__name__}, "
                                f"expected {child.output.__name__}"
                            ),
                        ),
                    )
                if len(self.graph.edges) == edges_before:
                    from .graph import to_mermaid_node

                    raise BuildError(
                        "sentinel_bypass",
                        f"composite {type(child).__name__}.forward returned without "
                        "invoking any child; the sentinel was not routed through the graph",
                        agent=callee,
                        mermaid=to_mermaid_node(
                            callee,
                            (child.input, child.output),
                            note="no child was invoked",
                        ),
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
    _needs_config = _is_default_forward(a) or getattr(a, "requires_config_at_build", False)
    if not a._children and a.config is None and _needs_config:
        from .graph import to_mermaid_node

        raise BuildError(
            "prompt_incomplete",
            "leaf agent requires `config`; pass one to the constructor",
            agent=type(a).__name__,
            mermaid=to_mermaid_node(
                type(a).__name__,
                (a.input, a.output),
                note="config is None",
            ),
        )


def _init_runner(
    a: Agent[Any, Any], *, cached_prompt: str | None = None
) -> None:
    """Construct the `StrandsRunner` for default-forward leaves only.

    Composites (agents that override ``forward``) don't need a runner;
    they route calls to their children and never invoke the model
    themselves.

    When `cached_prompt` is provided, `format_system_message()` is skipped
    and the cached string is used directly — the thaw path exercises this
    so a loaded agent doesn't re-render every leaf's system message.
    """
    if not _is_default_forward(a):
        return
    try:
        model = resolve_model(a.config)  # type: ignore[arg-type]
        if cached_prompt is None:
            rendered = a.format_system_message()
            if isinstance(rendered, list):
                rendered = "\n\n".join(
                    m.get("content", "")
                    for m in rendered
                    if m.get("role") == "system"
                )
            system_prompt = rendered or None
        else:
            system_prompt = cached_prompt or None
        object.__setattr__(
            a,
            "_runner",
            StrandsRunner(model=model, system_prompt=system_prompt),
        )
    except BuildError:
        raise
    except Exception as e:
        raise BuildError(
            "trace_failed",
            f"runner init failed: {e}",
            agent=type(a).__name__,
        ) from e


def _warn_shared_children(root: Agent[Any, Any]) -> None:
    """Emit a warning for any agent instance that appears under more than
    one parent attribute. Sharing is legal but hides mutation-coupling,
    so surface it.
    """
    parents_by_id: dict[int, list[str]] = {}
    queue: list[tuple[Agent[Any, Any], str]] = [(root, root.name)]
    visited: set[int] = {id(root)}
    while queue:
        parent, parent_path = queue.pop(0)
        for attr, child in parent._children.items():
            path = f"{parent_path}.{attr}"
            parents_by_id.setdefault(id(child), []).append(path)
            if id(child) not in visited:
                visited.add(id(child))
                queue.append((child, path))
    for parents in parents_by_id.values():
        if len(parents) > 1:
            warnings.warn(
                f"child agent is shared across paths: {', '.join(parents)}; "
                "mutation on the shared instance affects every occurrence",
                stacklevel=3,
            )


async def _trace(root: Agent[Any, Any], tracer: Tracer) -> Any:
    token = _TRACER.set(tracer)
    try:
        # Only composites get the payload-branch guard: they are supposed
        # to route on structure, not values. Custom-forward leaves are
        # pure computations and legitimately read input fields.
        if root._children:
            sentinel = _make_sentinel(root.input)  # type: ignore[arg-type]
            try:
                return await root.forward(sentinel)
            except (_PayloadBranchAccess, _PayloadBranchDunder) as exc:
                _raise_payload_branch(
                    exc,
                    agent_name=root.name,
                    composite_cls=type(root).__name__,
                    io=(root.input, root.output),  # type: ignore[arg-type]
                )
        sentinel = root.input.model_construct()  # type: ignore[union-attr]
        return await root.forward(sentinel)
    finally:
        _TRACER.reset(token)


async def abuild_agent(root: Agent[Any, Any]) -> Agent[Any, Any]:
    """Compile an agent architecture (async entry point).

    Passes run in order: validate → warn-on-shared-children → trace
    (composite roots only) → init-runner. Running `_init_runner` last
    means a failed trace leaves no leaf with a half-built runner.
    """
    for a in _tree(root):
        _validate(a)
    _warn_shared_children(root)

    tracer = Tracer(root)
    # Trace unless the root is a default-forward leaf — those need their
    # runner to be initialised before their forward can run, and since
    # they have no children there is no graph to record anyway.
    if root._children or not _is_default_forward(root):
        try:
            out = await _trace(root, tracer)
        except BuildError:
            raise
        except Exception as e:
            raise BuildError(
                "trace_failed", str(e), agent=root.name
            ) from e

        if not isinstance(out, root.output):  # type: ignore[arg-type]
            from .graph import to_mermaid_node

            raise BuildError(
                "output_mismatch",
                f"{root.name}.forward returned {type(out).__name__}, "
                f"expected {root.output.__name__}",  # type: ignore[union-attr]
                agent=root.name,
                mermaid=to_mermaid_node(
                    root.name,
                    (root.input, root.output),  # type: ignore[arg-type]
                    note=(
                        f"returned {type(out).__name__}, expected "
                        f"{root.output.__name__}"  # type: ignore[union-attr]
                    ),
                ),
            )
        if root._children and len(tracer.graph.edges) == 0:
            from .graph import to_mermaid_node

            raise BuildError(
                "sentinel_bypass",
                f"root composite {root.name}.forward returned without "
                "invoking any child; the sentinel was not routed through the graph",
                agent=root.name,
                mermaid=to_mermaid_node(
                    root.name,
                    (root.input, root.output),  # type: ignore[arg-type]
                    note="no child was invoked",
                ),
            )
    else:
        # Default-forward leaf root: trace is skipped (there's no graph to
        # capture), but verify the declared `output` can be round-tripped
        # as a Pydantic model so a malformed contract fails at build time
        # rather than on first invoke.
        try:
            root.output.model_construct()  # type: ignore[union-attr]
        except Exception as e:
            raise BuildError(
                "output_mismatch",
                f"leaf root {root.name}.output "
                f"({getattr(root.output, '__name__', root.output)!r}) "
                f"is not a usable Pydantic model: {e}",
                agent=root.name,
            ) from e

    for a in _tree(root):
        _init_runner(a)

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
