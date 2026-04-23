"""Export helpers for `AgentGraph` (Mermaid, JSON).

Free functions rather than methods on `AgentGraph` so that graph export
stays a pure view — adding new formats doesn't widen the data class.
"""

from __future__ import annotations

from typing import Any

from .build import AgentGraph, Edge, Node


def _mermaid_id(path: str) -> str:
    return path.replace(".", "_")


def _type_label(t: type) -> str:
    return getattr(t, "__name__", repr(t))


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
        "input": _type_label(n.input_type),
        "output": _type_label(n.output_type),
        "kind": n.kind,
    }


def _edge_json(e: Edge) -> dict[str, Any]:
    return {
        "caller": e.caller,
        "callee": e.callee,
        "input": _type_label(e.input_type),
        "output": _type_label(e.output_type),
    }


def to_json(graph: AgentGraph) -> dict[str, Any]:
    """Return a JSON-serializable dict describing the graph."""
    return {
        "root": graph.root,
        "nodes": [_node_json(n) for n in graph.nodes],
        "edges": [_edge_json(e) for e in graph.edges],
    }
