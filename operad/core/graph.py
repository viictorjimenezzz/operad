"""Export / round-trip helpers for `AgentGraph` (Mermaid, JSON).

Free functions rather than methods on `AgentGraph` so that graph
export stays a pure view — adding new formats doesn't widen the data
class. `to_json` emits fully qualified type names so that `from_json`
can rehydrate the exact same types, with a `TypeRegistry` as the
escape hatch when `importlib` lookup isn't enough.
"""

from __future__ import annotations

import enum
import importlib
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from .build import AgentGraph, Edge, Node
from .fields import is_system_field


def _mermaid_id(path: str) -> str:
    return path.replace(".", "_")


def _type_label(t: type) -> str:
    return getattr(t, "__name__", repr(t))


def _qualified_name(t: type) -> str:
    """Return `module.qualname` for round-trippable type references."""
    module = getattr(t, "__module__", "") or ""
    qualname = getattr(t, "__qualname__", None) or getattr(t, "__name__", "")
    return f"{module}.{qualname}" if module else qualname


def _annotation_label(annotation: Any) -> str:
    """Render a compact, readable annotation string for graph field metadata."""
    try:
        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is Literal:
            values = ",".join(repr(v) for v in args)
            return f"Literal[{values}]"

        if origin in (UnionType, Union):
            if len(args) == 2 and NoneType in args:
                inner = args[0] if args[1] is NoneType else args[1]
                return f"Optional[{_annotation_label(inner)}]"
            return " | ".join(_annotation_label(a) for a in args)

        if origin is list:
            inner = _annotation_label(args[0]) if args else "Any"
            return f"list[{inner}]"

        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return f"tuple[{_annotation_label(args[0])}, ...]"
            return f"tuple[{', '.join(_annotation_label(a) for a in args)}]"

        if origin is dict:
            left = _annotation_label(args[0]) if len(args) > 0 else "Any"
            right = _annotation_label(args[1]) if len(args) > 1 else "Any"
            return f"dict[{left}, {right}]"

        if origin is set:
            inner = _annotation_label(args[0]) if args else "Any"
            return f"set[{inner}]"

        if origin is frozenset:
            inner = _annotation_label(args[0]) if args else "Any"
            return f"frozenset[{inner}]"

        if origin is not None:
            origin_name = getattr(origin, "__name__", repr(origin))
            if args:
                return f"{origin_name}[{', '.join(_annotation_label(a) for a in args)}]"
            return origin_name

        if annotation is NoneType:
            return "None"

        if hasattr(annotation, "__name__"):
            return str(annotation.__name__)

        return repr(annotation)
    except Exception:
        return repr(annotation)


def _annotation_vocab(annotation: Any) -> list[Any] | None:
    """Best-effort enum/literal vocabulary for field metadata."""
    try:
        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is Literal:
            return [v for v in args]

        if origin in (UnionType, Union):
            vocab: list[Any] = []
            for a in args:
                sub = _annotation_vocab(a)
                if sub:
                    for item in sub:
                        if item not in vocab:
                            vocab.append(item)
            return vocab or None

        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return [m.value for m in annotation]

        return None
    except Exception:
        return None


def _jsonable_default(value: Any) -> Any:
    """Best-effort JSON-safe default for field metadata."""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_jsonable_default(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable_default(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable_default(v) for k, v in value.items()}
    return repr(value)


def _type_fields(model_cls: type) -> list[dict[str, Any]]:
    """Extract field metadata for a type node in `to_io_graph`."""
    if not isinstance(model_cls, type) or not issubclass(model_cls, BaseModel):
        return []

    rows: list[dict[str, Any]] = []
    for name, info in model_cls.model_fields.items():
        annotation = info.annotation
        required = bool(info.is_required())
        has_default = not required
        default_value: Any = None
        if has_default and info.default_factory is None:
            default_value = _jsonable_default(info.default)

        rows.append(
            {
                "name": name,
                "type": _annotation_label(annotation),
                "description": info.description or "",
                "system": is_system_field(info),
                "required": required,
                "has_default": has_default,
                "default": default_value,
                "enum_values": _annotation_vocab(annotation),
            }
        )
    return rows


def _nearest_composite_path(
    leaf_path: str,
    *,
    composite_paths: set[str],
    root_path: str,
) -> str | None:
    parts = leaf_path.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in composite_paths:
            return None if prefix == root_path else prefix
    return None


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


def to_io_graph(graph: AgentGraph) -> dict[str, Any]:
    """Inverted view: input/output types as nodes, agents as edges.

    Each leaf in the AgentGraph contributes one edge from its input-type
    node to its output-type node. Type nodes are deduplicated by qualified
    name. Composite nodes do not get their own edge or node; their path is
    exposed on descendant edges as ``composite_path`` for UI grouping.

    Returns:
        {
          "root": "<root agent class name>",
          "nodes": [
            {
              "key": "<module.qualname>",
              "name": "<class __name__>",
              "fields": [
                {
                  "name": "...",
                  "type": "...",
                  "description": "...",
                  "system": True | False,
                  "required": True | False,
                  "has_default": True | False,
                  "default": ...,
                  "enum_values": [... ] | None,
                },
                ...
              ],
            },
            ...
          ],
          "edges": [
            {
              "agent_path": "Root.stage_0.branch_1",
              "class_name": "<runtime class>",
              "kind": "leaf",
              "from": "<input qualified name>",
              "to": "<output qualified name>",
              "composite_path": "Root.stage_0" | None,
            },
            ...
          ]
        }
    """
    nodes_by_path = {n.path: n for n in graph.nodes}
    leaf_paths = {n.path for n in graph.nodes if n.kind == "leaf"}
    composite_paths = {n.path for n in graph.nodes if n.kind == "composite"}

    io_edges: list[dict[str, Any]] = []
    for e in graph.edges:
        if e.callee not in leaf_paths:
            continue
        node = nodes_by_path.get(e.callee)
        io_edges.append(
            {
                "agent_path": e.callee,
                "class_name": e.class_name
                or (node.class_name if node is not None else None)
                or e.callee.rsplit(".", 1)[-1],
                "kind": "leaf",
                "from": _qualified_name(e.input_type),
                "to": _qualified_name(e.output_type),
                "composite_path": _nearest_composite_path(
                    e.callee,
                    composite_paths=composite_paths,
                    root_path=graph.root,
                ),
            }
        )

    # Leaf roots have no recorded incoming edge in AgentGraph; synthesize one
    # so every leaf contributes one IO edge.
    root_node = nodes_by_path.get(graph.root)
    if root_node is not None and root_node.kind == "leaf":
        io_edges.append(
            {
                "agent_path": root_node.path,
                "class_name": root_node.class_name or root_node.path,
                "kind": "leaf",
                "from": _qualified_name(root_node.input_type),
                "to": _qualified_name(root_node.output_type),
                "composite_path": None,
            }
        )

    type_nodes: dict[str, dict[str, Any]] = {}
    for edge in io_edges:
        for end, side in ((edge["from"], "from"), (edge["to"], "to")):
            if end in type_nodes:
                continue
            t: type | None = None
            if side == "from":
                src = next((x for x in io_edges if x["from"] == end), None)
                if src is not None:
                    t = next(
                        (ge.input_type for ge in graph.edges if _qualified_name(ge.input_type) == end),
                        None,
                    )
            else:
                src = next((x for x in io_edges if x["to"] == end), None)
                if src is not None:
                    t = next(
                        (ge.output_type for ge in graph.edges if _qualified_name(ge.output_type) == end),
                        None,
                    )

            if t is None and root_node is not None:
                if _qualified_name(root_node.input_type) == end:
                    t = root_node.input_type
                elif _qualified_name(root_node.output_type) == end:
                    t = root_node.output_type

            if t is None:
                continue

            type_nodes[end] = {
                "key": end,
                "name": _type_label(t),
                "fields": _type_fields(t),
            }

    return {
        "root": graph.root,
        "nodes": list(type_nodes.values()),
        "edges": io_edges,
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
            class_name=n.get("class_name"),
        )
        for n in data["nodes"]
    ]
    edges = [
        Edge(
            caller=e["caller"],
            callee=e["callee"],
            input_type=reg.resolve(e["input"]),
            output_type=reg.resolve(e["output"]),
            class_name=e.get("class_name"),
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
