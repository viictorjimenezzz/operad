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
]
