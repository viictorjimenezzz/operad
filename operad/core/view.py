"""Views over `AgentGraph` for Mermaid, JSON, and IO-oriented displays."""

from __future__ import annotations

import enum
import importlib
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from .build import AgentGraph, Edge, Node
from .render import is_system_field


# ---------------------------------------------------------------------------
# Domain helpers.
# ---------------------------------------------------------------------------

_PIPELINE_KINDS = {"Sequential", "Parallel", "Router", "Loop"}


def _mermaid_id(path: str) -> str:
    return path.replace(".", "_")


def _type_label(t: type) -> str:
    return getattr(t, "__name__", repr(t))


def _dedupe_nodes(nodes: list[Node]) -> list[Node]:
    """Keep first-seen node per path for display/export stability."""
    seen: set[str] = set()
    out: list[Node] = []
    for n in nodes:
        if n.path in seen:
            continue
        seen.add(n.path)
        out.append(n)
    return out


def _dedupe_edges(edges: list[Edge]) -> list[Edge]:
    """Keep first-seen structural edge to avoid repeated Loop traces."""
    seen: set[tuple[str, str, type, type]] = set()
    out: list[Edge] = []
    for e in edges:
        key = (e.caller, e.callee, e.input_type, e.output_type)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _mermaid_node_label(n: Node) -> str:
    io = f"{_type_label(n.input_type)} -> {_type_label(n.output_type)}"
    if n.kind == "composite" and n.class_name in _PIPELINE_KINDS:
        return f"{n.class_name}<br/>{n.path}<br/>{io}"
    return f"{n.path}<br/>{io}"


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


def _build_composites(
    *,
    composite_paths: set[str],
    leaf_paths: set[str],
    composite_class_names: dict[str, str],
    root_path: str,
) -> list[dict[str, Any]]:
    """Return composite hierarchy for IO graph payloads (excludes the root).

    Each entry carries the composite's own ``parent_path`` (the nearest
    enclosing composite, or ``None`` if the immediate parent is the root)
    and ``children`` (paths of immediate composite or leaf descendants).
    """
    all_paths = composite_paths | leaf_paths
    out: list[dict[str, Any]] = []
    for c_path in sorted(composite_paths):
        if c_path == root_path:
            continue
        children: list[str] = []
        for p in all_paths:
            if p == c_path:
                continue
            np = _nearest_composite_path(
                p, composite_paths=composite_paths, root_path=root_path
            )
            if np == c_path:
                children.append(p)
        parent = _nearest_composite_path(
            c_path, composite_paths=composite_paths, root_path=root_path
        )
        out.append(
            {
                "path": c_path,
                "class_name": composite_class_names.get(c_path, "Composite"),
                "kind": "composite",
                "parent_path": parent,
                "children": sorted(children),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Mermaid view.
# ---------------------------------------------------------------------------


def _render_mermaid(graph: AgentGraph) -> str:
    """Render an `AgentGraph` as a Mermaid `flowchart LR`.

    Composite nodes (Sequential/Parallel/ReAct/etc., except the root) are
    emitted as Mermaid ``subgraph`` blocks containing their leaf descendants
    and any nested composite subgraphs. The root composite renders flat at
    the top level.
    """
    lines: list[str] = ["flowchart LR"]
    nodes = _dedupe_nodes(graph.nodes)
    edges = _dedupe_edges(graph.edges)
    classes: dict[str, list[str]] = {}

    composite_paths = {n.path for n in nodes if n.kind == "composite"}
    leaf_paths = {n.path for n in nodes if n.kind == "leaf"}
    nodes_by_path = {n.path: n for n in nodes}

    def _parent_of(path: str) -> str | None:
        return _nearest_composite_path(
            path, composite_paths=composite_paths, root_path=graph.root
        )

    children_by_parent: dict[str | None, list[str]] = {}
    for n in nodes:
        if n.path == graph.root:
            continue
        parent = _parent_of(n.path)
        children_by_parent.setdefault(parent, []).append(n.path)

    def _node_class(n: Node) -> str:
        if n.kind == "leaf":
            return "leafNode"
        if n.class_name in _PIPELINE_KINDS:
            return f"pipeline{n.class_name}"
        return "compositeNode"

    def _emit_node(n: Node, indent: str) -> None:
        nid = _mermaid_id(n.path)
        label = _mermaid_node_label(n)
        shape_open, shape_close = ("((", "))") if n.kind == "leaf" else ("[", "]")
        lines.append(f'{indent}{nid}{shape_open}"{label}"{shape_close}')
        classes.setdefault(_node_class(n), []).append(nid)

    def _emit_subgraph(composite_path: str, indent: str) -> None:
        n = nodes_by_path.get(composite_path)
        if n is None:
            return
        gid = _mermaid_id(composite_path)
        title = (n.class_name or composite_path).replace('"', "")
        lines.append(f'{indent}subgraph {gid}["{title}"]')
        # composite header: emit the composite itself as a small node so
        # callers/callees referencing the composite path resolve cleanly.
        _emit_node(n, indent + "    ")
        for child_path in children_by_parent.get(composite_path, []):
            child = nodes_by_path.get(child_path)
            if child is None:
                continue
            if child_path in composite_paths:
                _emit_subgraph(child_path, indent + "    ")
            else:
                _emit_node(child, indent + "    ")
        lines.append(f"{indent}end")

    # Emit root: render its node first, then its direct children (composites
    # become subgraphs, leaves stay flat at the root level).
    root_node = nodes_by_path.get(graph.root)
    if root_node is not None:
        _emit_node(root_node, "    ")
    for child_path in children_by_parent.get(None, []):
        child = nodes_by_path.get(child_path)
        if child is None:
            continue
        if child_path in composite_paths:
            _emit_subgraph(child_path, "    ")
        else:
            _emit_node(child, "    ")

    # Orphans: nodes that don't reach via the root traversal (defensive — e.g.
    # graphs without an explicit root entry). Emit them flat.
    rendered = {
        graph.root,
        *(p for p in composite_paths if p != graph.root),
        *leaf_paths,
    }
    for n in nodes:
        if n.path not in rendered:
            _emit_node(n, "    ")

    for e in edges:
        caller_id = _mermaid_id(e.caller)
        callee_id = _mermaid_id(e.callee)
        edge_label = f"{_type_label(e.input_type)} -> {_type_label(e.output_type)}"
        lines.append(f'    {caller_id} -->|"{edge_label}"| {callee_id}')

    lines.extend(
        [
            "    classDef compositeNode fill:#f8fafc,stroke:#334155,stroke-width:1px;",
            "    classDef leafNode fill:#ffffff,stroke:#334155,stroke-width:1px;",
            "    classDef pipelineSequential fill:#e8f3ff,stroke:#1d4ed8,stroke-width:1px;",
            "    classDef pipelineParallel fill:#ecfdf3,stroke:#15803d,stroke-width:1px;",
            "    classDef pipelineRouter fill:#fff7ed,stroke:#c2410c,stroke-width:1px;",
            "    classDef pipelineLoop fill:#f5f3ff,stroke:#6d28d9,stroke-width:1px;",
        ]
    )
    for cls, ids in classes.items():
        lines.append(f"    class {','.join(ids)} {cls}")

    return "\n".join(lines)


def _render_mermaid_edge(
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


def _render_mermaid_node(
    path: str, io: tuple[type, type], *, note: str | None = None
) -> str:
    """Render a single-node Mermaid fragment for BuildError footers.

    Used for errors with no failing edge (e.g. `router_miss`: the Router
    received a label no branch matched). When `note` is given it is
    appended as a second line inside the node label.
    """
    nid = _mermaid_id(path)
    label = f"{path}<br/>{_type_label(io[0])} -> {_type_label(io[1])}"
    if note is not None:
        label = f"{label}<br/>❌ {note}"
    return "flowchart LR\n" + f'    {nid}["{label}"]'


# ---------------------------------------------------------------------------
# JSON graph view.
# ---------------------------------------------------------------------------


def _node_json(n: Node) -> dict[str, Any]:
    return {
        "path": n.path,
        "input": _qualified_name(n.input_type),
        "output": _qualified_name(n.output_type),
        "kind": n.kind,
        "class_name": n.class_name,
        "input_fields": _type_fields(n.input_type),
        "output_fields": _type_fields(n.output_type),
    }


def _edge_json(e: Edge) -> dict[str, Any]:
    return {
        "caller": e.caller,
        "callee": e.callee,
        "input": _qualified_name(e.input_type),
        "output": _qualified_name(e.output_type),
        "class_name": e.class_name,
    }


def to_json(graph: AgentGraph) -> dict[str, Any]:
    """Return a JSON-serializable dict describing the graph.

    Type fields use qualified `module.qualname` strings so that
    `from_json` can rehydrate the same class references; per-node
    ``class_name``, ``input_fields`` and ``output_fields`` are also
    embedded so consumers in a different process (e.g. the dashboard)
    can produce the rich :func:`to_io_graph` view without round-tripping
    types through ``importlib``.
    """
    return {
        "root": graph.root,
        "nodes": [_node_json(n) for n in graph.nodes],
        "edges": [_edge_json(e) for e in graph.edges],
    }


# ---------------------------------------------------------------------------
# IO graph view.
# ---------------------------------------------------------------------------


def _render_io_graph(graph: AgentGraph) -> dict[str, Any]:
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

    composite_class_names = {
        n.path: n.class_name or "Composite"
        for n in graph.nodes
        if n.kind == "composite"
    }
    composites = _build_composites(
        composite_paths=composite_paths,
        leaf_paths=leaf_paths,
        composite_class_names=composite_class_names,
        root_path=graph.root,
    )

    return {
        "root": graph.root,
        "nodes": list(type_nodes.values()),
        "edges": io_edges,
        "composites": composites,
    }


def _render_io_graph_from_json(graph_json: dict[str, Any]) -> dict[str, Any]:
    """JSON-only equivalent of :func:`to_io_graph`.

    The full :func:`to_io_graph` walks live Pydantic classes to extract
    field metadata. That requires :func:`from_json` to round-trip the
    type names back to the originating classes — which fails across
    process boundaries (the dashboard cannot import ``__main__.Foo``
    from a separate demo process).

    This function operates on the JSON shape produced by :func:`to_json`
    and uses the embedded ``class_name`` / ``input_fields`` /
    ``output_fields`` keys directly. It is the canonical path for any
    consumer that does not have access to the live type objects.
    """
    nodes = [n for n in graph_json.get("nodes") or [] if isinstance(n, dict)]
    edges = [e for e in graph_json.get("edges") or [] if isinstance(e, dict)]
    leaf_paths = {n["path"] for n in nodes if n.get("kind") == "leaf" and "path" in n}
    composite_paths = {n["path"] for n in nodes if n.get("kind") == "composite" and "path" in n}
    nodes_by_path = {n["path"]: n for n in nodes if "path" in n}
    root = str(graph_json.get("root") or "")

    def _coerce_fields(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        return [f for f in raw if isinstance(f, dict)]

    io_edges: list[dict[str, Any]] = []
    for e in edges:
        callee = str(e.get("callee") or "")
        if callee not in leaf_paths:
            continue
        node = nodes_by_path.get(callee, {})
        io_edges.append(
            {
                "agent_path": callee,
                "class_name": e.get("class_name")
                or node.get("class_name")
                or callee.rsplit(".", 1)[-1],
                "kind": "leaf",
                "from": str(e.get("input") or ""),
                "to": str(e.get("output") or ""),
                "composite_path": _nearest_composite_path(
                    callee,
                    composite_paths=composite_paths,
                    root_path=root,
                ),
            }
        )

    root_node = nodes_by_path.get(root) if root else None
    if root_node and root_node.get("kind") == "leaf":
        io_edges.append(
            {
                "agent_path": root_node["path"],
                "class_name": root_node.get("class_name") or root_node["path"],
                "kind": "leaf",
                "from": str(root_node.get("input") or ""),
                "to": str(root_node.get("output") or ""),
                "composite_path": None,
            }
        )

    type_nodes: dict[str, dict[str, Any]] = {}
    for edge in io_edges:
        for end_key, side in ((edge["from"], "input"), (edge["to"], "output")):
            if not end_key or end_key in type_nodes:
                continue
            fields_key = f"{side}_fields"
            chosen_fields: list[dict[str, Any]] = []
            chosen_name: str | None = None
            for n in nodes:
                if n.get(side) == end_key:
                    if not chosen_fields:
                        chosen_fields = _coerce_fields(n.get(fields_key))
                    chosen_name = chosen_name or n.get(f"{side}_name")
                    if chosen_fields:
                        break
            type_nodes[end_key] = {
                "key": end_key,
                "name": chosen_name or end_key.rsplit(".", 1)[-1],
                "fields": chosen_fields,
            }

    composite_class_names = {
        str(n["path"]): str(n.get("class_name") or "Composite")
        for n in nodes
        if n.get("kind") == "composite" and "path" in n
    }
    composites = _build_composites(
        composite_paths=composite_paths,
        leaf_paths=leaf_paths,
        composite_class_names=composite_class_names,
        root_path=root,
    )

    return {
        "root": root or None,
        "nodes": list(type_nodes.values()),
        "edges": io_edges,
        "composites": composites,
    }


# ---------------------------------------------------------------------------
# View classes.
# ---------------------------------------------------------------------------


class MermaidView:
    """Render build graphs as Mermaid flowcharts."""

    def render(self, graph: AgentGraph) -> str:
        return _render_mermaid(graph)

    def render_edge(
        self,
        caller: str,
        callee: str,
        callee_io: tuple[type, type],
        *,
        caller_io: tuple[type, type] | None = None,
        note: str | None = None,
    ) -> str:
        return _render_mermaid_edge(
            caller,
            callee,
            callee_io,
            caller_io=caller_io,
            note=note,
        )

    def render_node(
        self,
        path: str,
        io: tuple[type, type],
        *,
        note: str | None = None,
    ) -> str:
        return _render_mermaid_node(path, io, note=note)


class IOView:
    """Render build graphs as input/output type nodes plus agent edges."""

    def render(self, graph: AgentGraph) -> dict[str, Any]:
        return _render_io_graph(graph)

    def render_json(self, graph_json: dict[str, Any]) -> dict[str, Any]:
        return _render_io_graph_from_json(graph_json)


_MERMAID_VIEW = MermaidView()
_IO_VIEW = IOView()


# ---------------------------------------------------------------------------
# Public wrappers.
# ---------------------------------------------------------------------------


def to_mermaid(graph: AgentGraph) -> str:
    return _MERMAID_VIEW.render(graph)


def to_mermaid_edge(
    caller: str,
    callee: str,
    callee_io: tuple[type, type],
    *,
    caller_io: tuple[type, type] | None = None,
    note: str | None = None,
) -> str:
    return _MERMAID_VIEW.render_edge(
        caller,
        callee,
        callee_io,
        caller_io=caller_io,
        note=note,
    )


def to_mermaid_node(
    path: str, io: tuple[type, type], *, note: str | None = None
) -> str:
    return _MERMAID_VIEW.render_node(path, io, note=note)


def to_io_graph(graph: AgentGraph) -> dict[str, Any]:
    return _IO_VIEW.render(graph)


def to_io_graph_from_json(graph_json: dict[str, Any]) -> dict[str, Any]:
    return _IO_VIEW.render_json(graph_json)


# ---------------------------------------------------------------------------
# Round-trip.
# ---------------------------------------------------------------------------


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


def to_agent_graph(graph: AgentGraph) -> dict[str, Any]:
    """Render an `AgentGraph` in agent-flow shape: agents as nodes, types as edges.

    This is the dual of :func:`to_io_graph`. Where the IO view treats data
    types as nodes and agents as edges (a dataflow projection), the
    agent-flow view treats agents as nodes (each leaf and composite gets a
    node) and the type that flows along each invocation edge becomes the
    edge label. Composites carry ``parent_path`` so callers can render a
    nested hierarchy with composite groups containing their children.

    Output shape:
        {
          "root": "<root agent path>",
          "nodes": [
            {
              "path": "Root.stage_0.reason",
              "class_name": "Reasoner",
              "kind": "leaf" | "composite",
              "parent_path": "Root.stage_0" | None,
              "input": "module.qualname",
              "output": "module.qualname",
              "input_label": "Question",
              "output_label": "Answer",
            },
            ...
          ],
          "edges": [
            {
              "caller": "Root.stage_0.reason",
              "callee": "Root.stage_0.act",
              "type": "Thought",
              "input": "module.qualname",
              "output": "module.qualname",
            },
            ...
          ]
        }
    """
    composite_paths = {n.path for n in graph.nodes if n.kind == "composite"}

    def _parent(path: str) -> str | None:
        if path == graph.root:
            return None
        # walk up via dot-segments and pick the closest enclosing composite
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in composite_paths:
                return prefix
        return None

    nodes_out = [
        {
            "path": n.path,
            "class_name": n.class_name or n.path.rsplit(".", 1)[-1],
            "kind": n.kind,
            "parent_path": _parent(n.path),
            "input": _qualified_name(n.input_type),
            "output": _qualified_name(n.output_type),
            "input_label": _type_label(n.input_type),
            "output_label": _type_label(n.output_type),
        }
        for n in _dedupe_nodes(graph.nodes)
    ]

    edges_out = [
        {
            "caller": e.caller,
            "callee": e.callee,
            "type": _type_label(e.input_type),
            "input": _qualified_name(e.input_type),
            "output": _qualified_name(e.output_type),
        }
        for e in _dedupe_edges(graph.edges)
    ]

    return {"root": graph.root, "nodes": nodes_out, "edges": edges_out}


def to_agent_graph_from_json(graph_json: dict[str, Any]) -> dict[str, Any]:
    """JSON-only equivalent of :func:`to_agent_graph` for out-of-process consumers."""
    nodes = [n for n in graph_json.get("nodes") or [] if isinstance(n, dict)]
    edges = [e for e in graph_json.get("edges") or [] if isinstance(e, dict)]
    composite_paths = {
        n["path"] for n in nodes if n.get("kind") == "composite" and "path" in n
    }
    root = str(graph_json.get("root") or "")

    def _parent(path: str) -> str | None:
        if path == root:
            return None
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in composite_paths:
                return prefix
        return None

    def _short(qual: str) -> str:
        return qual.rsplit(".", 1)[-1] if qual else ""

    nodes_out: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for n in nodes:
        path = n.get("path")
        if not isinstance(path, str) or path in seen_paths:
            continue
        seen_paths.add(path)
        nodes_out.append(
            {
                "path": path,
                "class_name": n.get("class_name") or path.rsplit(".", 1)[-1],
                "kind": n.get("kind") or "leaf",
                "parent_path": _parent(path),
                "input": str(n.get("input") or ""),
                "output": str(n.get("output") or ""),
                "input_label": _short(str(n.get("input") or "")),
                "output_label": _short(str(n.get("output") or "")),
            }
        )

    edges_out: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, str]] = set()
    for e in edges:
        caller = str(e.get("caller") or "")
        callee = str(e.get("callee") or "")
        in_q = str(e.get("input") or "")
        out_q = str(e.get("output") or "")
        key = (caller, callee, in_q, out_q)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges_out.append(
            {
                "caller": caller,
                "callee": callee,
                "type": _short(in_q),
                "input": in_q,
                "output": out_q,
            }
        )

    return {"root": root or None, "nodes": nodes_out, "edges": edges_out}


__all__ = [
    "IOView",
    "MermaidView",
    "TypeRegistry",
    "from_json",
    "to_agent_graph",
    "to_agent_graph_from_json",
    "to_io_graph",
    "to_io_graph_from_json",
    "to_json",
    "to_mermaid",
    "to_mermaid_edge",
    "to_mermaid_node",
]
