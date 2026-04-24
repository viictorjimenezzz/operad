"""Export / round-trip helpers for `AgentGraph` (Mermaid, JSON).

Free functions rather than methods on `AgentGraph` so that graph
export stays a pure view — adding new formats doesn't widen the data
class. `to_json` emits fully qualified type names so that `from_json`
can rehydrate the exact same types, with a `TypeRegistry` as the
escape hatch when `importlib` lookup isn't enough.
"""

from __future__ import annotations

import importlib
from typing import Any

from .build import AgentGraph, Edge, Node


def _mermaid_id(path: str) -> str:
    return path.replace(".", "_")


def _type_label(t: type) -> str:
    return getattr(t, "__name__", repr(t))


def _qualified_name(t: type) -> str:
    """Return `module.qualname` for round-trippable type references."""
    module = getattr(t, "__module__", "") or ""
    qualname = getattr(t, "__qualname__", None) or getattr(t, "__name__", "")
    return f"{module}.{qualname}" if module else qualname


def to_mermaid(graph: AgentGraph) -> str:
    """Render an `AgentGraph` as a Mermaid `flowchart LR`."""
    lines: list[str] = ["flowchart LR"]
    for n in graph.nodes:
        nid = _mermaid_id(n.path)
        label = f"{n.path}<br/>{_type_label(n.input_type)} -> {_type_label(n.output_type)}"
        shape_open, shape_close = ("((", "))") if n.kind == "leaf" else ("[", "]")
        lines.append(f'    {nid}{shape_open}"{label}"{shape_close}')
    for e in graph.edges:
        caller_id = _mermaid_id(e.caller)
        callee_id = _mermaid_id(e.callee)
        edge_label = f"{_type_label(e.input_type)} -> {_type_label(e.output_type)}"
        lines.append(f'    {caller_id} -->|"{edge_label}"| {callee_id}')
    return "\n".join(lines)


def to_mermaid_edge(
    caller: str,
    callee: str,
    callee_io: tuple[type, type],
    *,
    caller_io: tuple[type, type] | None = None,
    note: str | None = None,
) -> str:
    """Render a two-node, one-edge Mermaid fragment for BuildError footers.

    The edge is marked with ❌ to draw the reader's eye to the failing
    hand-off. When `caller_io` is None the caller is rendered as a bare
    label (e.g. the composite root whose own `forward` returned the wrong
    type); otherwise both endpoints carry `In -> Out` labels.
    """
    caller_id = _mermaid_id(caller)
    callee_id = _mermaid_id(callee)
    if caller_io is not None:
        caller_label = (
            f"{caller}<br/>{_type_label(caller_io[0])} -> "
            f"{_type_label(caller_io[1])}"
        )
    else:
        caller_label = caller
    callee_label = (
        f"{callee}<br/>{_type_label(callee_io[0])} -> "
        f"{_type_label(callee_io[1])}"
    )
    edge_label = "❌" if note is None else f"❌ {note}"
    lines = [
        "flowchart LR",
        f'    {caller_id}["{caller_label}"]',
        f'    {callee_id}["{callee_label}"]',
        f'    {caller_id} -->|"{edge_label}"| {callee_id}',
    ]
    return "\n".join(lines)


def to_mermaid_node(
    path: str, io: tuple[type, type], *, note: str | None = None
) -> str:
    """Render a single-node Mermaid fragment for BuildError footers.

    Used for errors with no failing edge (e.g. `router_miss`: the Switch
    received a label no branch matched). When `note` is given it is
    appended as a second line inside the node label.
    """
    nid = _mermaid_id(path)
    label = f"{path}<br/>{_type_label(io[0])} -> {_type_label(io[1])}"
    if note is not None:
        label = f"{label}<br/>❌ {note}"
    return "flowchart LR\n" + f'    {nid}["{label}"]'


def _node_json(n: Node) -> dict[str, Any]:
    return {
        "path": n.path,
        "input": _qualified_name(n.input_type),
        "output": _qualified_name(n.output_type),
        "kind": n.kind,
    }


def _edge_json(e: Edge) -> dict[str, Any]:
    return {
        "caller": e.caller,
        "callee": e.callee,
        "input": _qualified_name(e.input_type),
        "output": _qualified_name(e.output_type),
    }


def to_json(graph: AgentGraph) -> dict[str, Any]:
    """Return a JSON-serializable dict describing the graph.

    Type fields use qualified `module.qualname` strings so that
    `from_json` can rehydrate the same class references.
    """
    return {
        "root": graph.root,
        "nodes": [_node_json(n) for n in graph.nodes],
        "edges": [_edge_json(e) for e in graph.edges],
    }


# --- round-trip -------------------------------------------------------------


class TypeRegistry:
    """Name → type lookup for `from_json`.

    Populated explicitly for types whose `module.qualname` lookup via
    `importlib` doesn't work (dynamically created types, test fixtures
    in non-importable modules, etc.).
    """

    def __init__(self) -> None:
        self._types: dict[str, type] = {}

    def register(self, t: type, *, name: str | None = None) -> None:
        key = name if name is not None else _qualified_name(t)
        self._types[key] = t

    def resolve(self, name: str) -> type:
        if name in self._types:
            return self._types[name]
        if "." not in name:
            raise KeyError(f"unregistered type: {name!r}")
        module_name, _, qualname = name.rpartition(".")
        module = importlib.import_module(module_name)
        obj: Any = module
        for part in qualname.split("."):
            obj = getattr(obj, part)
        return obj  # type: ignore[no-any-return]


def from_json(
    data: dict[str, Any], registry: TypeRegistry | None = None
) -> AgentGraph:
    """Rehydrate an `AgentGraph` from `to_json` output.

    `registry` is consulted first for any type name; unknown names fall
    back to `importlib` on the `module.qualname` pair.
    """
    reg = registry if registry is not None else TypeRegistry()
    nodes = [
        Node(
            path=n["path"],
            input_type=reg.resolve(n["input"]),
            output_type=reg.resolve(n["output"]),
            kind=n["kind"],
        )
        for n in data["nodes"]
    ]
    edges = [
        Edge(
            caller=e["caller"],
            callee=e["callee"],
            input_type=reg.resolve(e["input"]),
            output_type=reg.resolve(e["output"]),
        )
        for e in data["edges"]
    ]
    return AgentGraph(root=data["root"], nodes=nodes, edges=edges)


__all__ = [
    "TypeRegistry",
    "from_json",
    "to_json",
    "to_mermaid",
    "to_mermaid_edge",
    "to_mermaid_node",
]
