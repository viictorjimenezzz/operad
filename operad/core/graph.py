"""Export / round-trip helpers for `AgentGraph` (Mermaid, JSON).

Free functions rather than methods on `AgentGraph` so that graph
export stays a pure view — adding new formats doesn't widen the data
class. `to_json` emits fully qualified type names so that `from_json`
can rehydrate the exact same types, with a `TypeRegistry` as the
escape hatch when `importlib` lookup isn't enough.
"""

from __future__ import annotations

import importlib
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from .fields import is_system_field

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


def _annotation_name(annotation: Any) -> str:
    if annotation is Any:
        return "Any"
    if annotation is None:
        return "None"
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is None:
        if isinstance(annotation, type):
            return annotation.__name__
        raw = str(annotation)
        return raw.replace("typing.", "")
    if origin in {Union, UnionType}:
        names = [_annotation_name(a) for a in args]
        non_none = [n for n in names if n != "None"]
        if len(non_none) + 1 == len(names) and "None" in names:
            return f"Optional[{non_none[0]}]" if non_none else "Optional[Any]"
        return f"Union[{', '.join(names)}]"
    if origin is Literal:
        vals = ",".join(repr(a) for a in args)
        return f"Literal[{vals}]"
    origin_name = getattr(origin, "__name__", str(origin).replace("typing.", ""))
    if args:
        return f"{origin_name}[{', '.join(_annotation_name(a) for a in args)}]"
    return origin_name


def _type_fields(t: type) -> list[dict[str, Any]]:
    if not isinstance(t, type):
        return []
    if not issubclass(t, BaseModel):
        return []
    out: list[dict[str, Any]] = []
    for name, info in t.model_fields.items():
        out.append(
            {
                "name": name,
                "type": _annotation_name(info.annotation),
                "description": info.description or "",
                "system": is_system_field(info),
            }
        )
    return out


def _type_node(t: type) -> dict[str, Any]:
    key = _qualified_name(t)
    name = getattr(t, "__name__", key.rsplit(".", 1)[-1])
    return {
        "key": key,
        "name": name,
        "fields": _type_fields(t),
    }


def _nearest_composite(
    leaf_path: str, *, root: str, composites: set[str]
) -> str | None:
    parts = leaf_path.split(".")
    if len(parts) < 2:
        return None
    nearest: str | None = None
    for i in range(1, len(parts)):
        prefix = ".".join(parts[:i])
        if prefix in composites:
            nearest = prefix
    if nearest is None or nearest == root:
        return None
    return nearest


def to_io_graph(graph: AgentGraph) -> dict[str, Any]:
    """Inverted view: input/output types as nodes, leaves as typed edges.

    Type nodes are deduplicated by ``module.qualname``. Composite graph nodes
    are not emitted as edges; each leaf contributes one edge from its input
    type node to its output type node.
    """
    composite_paths = {n.path for n in graph.nodes if n.kind == "composite"}
    type_nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for node in graph.nodes:
        if node.kind != "leaf":
            continue
        from_key = _qualified_name(node.input_type)
        to_key = _qualified_name(node.output_type)
        if from_key not in type_nodes:
            type_nodes[from_key] = _type_node(node.input_type)
        if to_key not in type_nodes:
            type_nodes[to_key] = _type_node(node.output_type)
        edges.append(
            {
                "agent_path": node.path,
                "class_name": node.path.rsplit(".", 1)[-1],
                "kind": "leaf",
                "from": from_key,
                "to": to_key,
                "composite_path": _nearest_composite(
                    node.path, root=graph.root, composites=composite_paths
                ),
            }
        )

    return {
        "root": graph.root,
        "nodes": list(type_nodes.values()),
        "edges": edges,
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
    "to_io_graph",
    "to_json",
    "to_mermaid",
    "to_mermaid_edge",
    "to_mermaid_node",
]
