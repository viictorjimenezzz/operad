"""Freeze / thaw a built ``Agent`` to a single JSON file.

Freeze captures the three pieces of a compiled agent that are expensive
to recreate: the declared state (via ``AgentState``), the computation
graph (via ``to_json``), and each default-forward leaf's rendered system
message. Custom-forward agents (composites like ``Pipeline``,
user-defined custom leaves with per-instance state like ``FakeLeaf``)
also carry a small pickled blob of their routing / instance state, with
intra-tree ``Agent`` references rewritten to ``_ChildRef`` sentinels so
thaw can redirect them at the newly-reconstructed children.

v1 limitations (raise ``BuildError`` at freeze time, not thaw):
- Non-pickleable callables in routing state (lambdas defined in
  ``__main__``, closures over unpicklable objects).
- ``Agent`` references embedded in containers other than ``list``,
  ``tuple``, or ``dict`` values.
- Cross-version thaw: rejected when the frozen
  ``operad_version_hash`` / ``python_version_hash`` don't match.
"""

from __future__ import annotations

import base64
import importlib
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils.errors import BuildError
from .agent import Agent, _labelled_tree, _system_to_str
from .example import Example
from .graph import from_json, to_json
from .output import OPERAD_VERSION_HASH, PYTHON_VERSION_HASH
from .state import AgentState


_KNOWN_AGENT_ATTRS: frozenset[str] = frozenset(
    {
        "role",
        "task",
        "rules",
        "examples",
        "config",
        "input",
        "output",
        "_children",
        "_built",
        "_graph",
    }
)


@dataclass(frozen=True)
class _ChildRef:
    """Sentinel marking where a child Agent was in routing state.

    At freeze time, every intra-tree ``Agent`` reference in a composite's
    routing dict is substituted with ``_ChildRef(attr_name)``. At thaw
    time, the sentinel is resolved against the reconstructed parent's
    ``_children`` dict so references point at the new instances.
    """

    attr: str


def _is_default_forward(a: Agent) -> bool:
    return type(a).forward is Agent.forward


def _qualified_class_name(cls: type) -> str:
    module = getattr(cls, "__module__", "") or ""
    qualname = getattr(cls, "__qualname__", None) or getattr(cls, "__name__", "")
    return f"{module}.{qualname}" if module else qualname


def _resolve_class(qualname: str) -> type:
    module_name, _, rest = qualname.rpartition(".")
    if not module_name:
        raise BuildError(
            "not_built",
            f"cannot resolve frozen class {qualname!r}: not dotted",
        )
    module = importlib.import_module(module_name)
    obj: Any = module
    for part in rest.split("."):
        obj = getattr(obj, part)
    return obj  # type: ignore[no-any-return]


# --- extra-state capture ----------------------------------------------------


def _substitute_refs(
    value: Any, children_by_id: dict[int, str], path: str, attr: str
) -> Any:
    """Walk `value`; replace any in-tree Agent with a `_ChildRef`.

    Raises `BuildError("not_built", ...)` if an Agent is found inside a
    container we don't know how to traverse safely (dataclasses, sets,
    user objects) — better an honest failure than a silent mis-freeze.
    """
    if isinstance(value, Agent):
        name = children_by_id.get(id(value))
        if name is None:
            raise BuildError(
                "not_built",
                f"cannot freeze: {path}.{attr} references an Agent "
                "outside this parent's children",
                agent=path,
            )
        return _ChildRef(attr=name)
    if isinstance(value, list):
        return [
            _substitute_refs(v, children_by_id, path, attr) for v in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _substitute_refs(v, children_by_id, path, attr) for v in value
        )
    if isinstance(value, dict):
        return {
            k: _substitute_refs(v, children_by_id, path, attr)
            for k, v in value.items()
        }
    if isinstance(value, (set, frozenset)):
        for item in value:
            if isinstance(item, Agent):
                raise BuildError(
                    "not_built",
                    f"cannot freeze: {path}.{attr} contains an Agent "
                    "inside a set (unsupported container)",
                    agent=path,
                )
        return value
    return value


def _resolve_refs(value: Any, children: dict[str, Agent]) -> Any:
    """Inverse of `_substitute_refs` at thaw time."""
    if isinstance(value, _ChildRef):
        return children[value.attr]
    if isinstance(value, list):
        return [_resolve_refs(v, children) for v in value]
    if isinstance(value, tuple):
        return tuple(_resolve_refs(v, children) for v in value)
    if isinstance(value, dict):
        return {k: _resolve_refs(v, children) for k, v in value.items()}
    return value


def _extra_attrs(a: Agent) -> dict[str, Any]:
    """Attributes that live on a custom-forward agent outside AgentState.

    For default-forward leaves we return ``{}``; their non-standard
    ``__dict__`` entries are strands-owned and get rebuilt by
    ``_init_strands`` on thaw.
    """
    if _is_default_forward(a):
        return {}
    children = a._children
    return {
        name: value
        for name, value in a.__dict__.items()
        if name not in _KNOWN_AGENT_ATTRS and name not in children
    }


# --- freeze -----------------------------------------------------------------


def _redact_state(state: AgentState) -> AgentState:
    """Return a copy of `state` with every `config.api_key` zeroed."""
    cfg = state.config
    if cfg is not None and getattr(cfg, "api_key", None) is not None:
        cfg = cfg.model_copy(update={"api_key": None})
    return AgentState(
        class_name=state.class_name,
        role=state.role,
        task=state.task,
        rules=list(state.rules),
        examples=[dict(e) for e in state.examples],
        config=cfg,
        input_type_name=state.input_type_name,
        output_type_name=state.output_type_name,
        children={k: _redact_state(v) for k, v in state.children.items()},
    )


def freeze_agent(agent: Agent, path: str | Path) -> None:
    """Persist a built `agent` to `path` as a single JSON file.

    See module docstring for the format and v1 limitations.
    """
    if not agent._built:
        raise BuildError(
            "not_built",
            f"cannot freeze {type(agent).__name__}: call .build() first",
            agent=type(agent).__name__,
        )

    class_map: dict[str, str] = {}
    routing: dict[str, str] = {}
    prompts: dict[str, Any] = {}

    for qual_path, node in _labelled_tree(agent):
        class_map[qual_path] = _qualified_class_name(type(node))

        if not _is_default_forward(node):
            raw = _extra_attrs(node)
            children_by_id = {id(v): k for k, v in node._children.items()}
            substituted = {
                k: _substitute_refs(v, children_by_id, qual_path, k)
                for k, v in raw.items()
            }
            try:
                blob = pickle.dumps(substituted)
            except Exception as e:
                raise BuildError(
                    "not_built",
                    f"cannot freeze {qual_path}: routing state is not "
                    f"pickleable: {e}",
                    agent=qual_path,
                ) from e
            routing[qual_path] = base64.b64encode(blob).decode("ascii")
        elif not node._children:
            # Default-forward leaf: cache its rendered system message.
            prompts[qual_path] = _system_to_str(node.format_system_message())

    state = _redact_state(agent.state())
    graph_json = to_json(agent._graph) if agent._graph is not None else None

    payload = {
        "operad_version_hash": OPERAD_VERSION_HASH,
        "python_version_hash": PYTHON_VERSION_HASH,
        "agent_class": _qualified_class_name(type(agent)),
        "class_map": class_map,
        "state": state.model_dump(mode="json"),
        "graph": graph_json,
        "prompts": prompts,
        "routing": routing,
    }

    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8"
    )


# --- thaw -------------------------------------------------------------------


def _new_agent(cls: type, state: AgentState, io: tuple[type, type]) -> Agent:
    """Construct an unbuilt instance of `cls` by bypassing its `__init__`.

    We set only the attributes `Agent.__init__` would set; children and
    extra state are wired on afterwards.
    """
    obj: Agent = cls.__new__(cls)  # type: ignore[call-arg]
    object.__setattr__(obj, "_children", {})
    object.__setattr__(obj, "_built", False)
    object.__setattr__(obj, "_graph", None)
    obj.input = io[0]  # type: ignore[assignment]
    obj.output = io[1]  # type: ignore[assignment]
    obj.role = state.role
    obj.task = state.task
    obj.rules = list(state.rules)
    obj.config = (
        state.config.model_copy(deep=True) if state.config is not None else None
    )
    obj.examples = [
        Example(
            input=io[0].model_validate(e["input"]),
            output=io[1].model_validate(e["output"]),
        )
        for e in state.examples
    ]
    return obj


def _io_from_graph(
    graph_json: dict[str, Any] | None,
) -> dict[str, tuple[type, type]]:
    """Return `{qualified_path: (input_type, output_type)}` from graph JSON."""
    if graph_json is None:
        return {}
    g = from_json(graph_json)
    return {n.path: (n.input_type, n.output_type) for n in g.nodes}


def _reconstruct(
    state: AgentState,
    qual_path: str,
    class_map: dict[str, str],
    io_map: dict[str, tuple[type, type]],
) -> Agent:
    qualname = class_map.get(qual_path)
    if qualname is None:
        raise BuildError(
            "not_built",
            f"frozen file missing class_map entry for {qual_path!r}",
        )
    cls = _resolve_class(qualname)
    io = io_map.get(qual_path)
    if io is None:
        # Leaf-root agents aren't captured in a graph. Fall back to the
        # class-level ClassVars; raise if those aren't set.
        class_input = getattr(cls, "input", None)
        class_output = getattr(cls, "output", None)
        if class_input is None or class_output is None:
            raise BuildError(
                "not_built",
                f"cannot thaw {qual_path}: no graph entry and no class-"
                f"level input/output on {qualname}",
            )
        io = (class_input, class_output)
    agent = _new_agent(cls, state, io)
    for attr, child_state in state.children.items():
        child_path = f"{qual_path}.{attr}"
        child = _reconstruct(child_state, child_path, class_map, io_map)
        setattr(agent, attr, child)
    return agent


def _restore_extra(
    agent: Agent,
    qual_path: str,
    routing: dict[str, str],
) -> None:
    """Reinstate non-standard attributes on `agent` and its descendants."""
    if not _is_default_forward(agent):
        blob_b64 = routing.get(qual_path)
        if blob_b64 is not None:
            blob = base64.b64decode(blob_b64.encode("ascii"))
            try:
                extras = pickle.loads(blob)
            except Exception as e:
                raise BuildError(
                    "not_built",
                    f"cannot thaw {qual_path}: unpickle failed: {e}",
                    agent=qual_path,
                ) from e
            for name, value in extras.items():
                resolved = _resolve_refs(value, agent._children)
                object.__setattr__(agent, name, resolved)
    for attr, child in agent._children.items():
        _restore_extra(child, f"{qual_path}.{attr}", routing)


def thaw_agent(path: str | Path) -> Agent:
    """Reconstitute a built agent previously written with `freeze_agent`."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)

    if data.get("operad_version_hash") != OPERAD_VERSION_HASH:
        raise BuildError(
            "not_built",
            "frozen agent has different operad version: stored "
            f"{data.get('operad_version_hash')!r}, current "
            f"{OPERAD_VERSION_HASH!r}",
        )
    if data.get("python_version_hash") != PYTHON_VERSION_HASH:
        raise BuildError(
            "not_built",
            "frozen agent has different python version: stored "
            f"{data.get('python_version_hash')!r}, current "
            f"{PYTHON_VERSION_HASH!r}",
        )

    class_map: dict[str, str] = data["class_map"]
    routing: dict[str, str] = data.get("routing", {})
    prompts: dict[str, Any] = data.get("prompts", {})
    graph_json: dict[str, Any] | None = data.get("graph")
    io_map = _io_from_graph(graph_json)

    root_state = AgentState.model_validate(data["state"])
    root_path = _resolve_class(data["agent_class"]).__name__
    root = _reconstruct(root_state, root_path, class_map, io_map)

    _restore_extra(root, root_path, routing)

    if graph_json is not None:
        object.__setattr__(root, "_graph", from_json(graph_json))

    # Re-wire strands for every default-forward leaf, using the cached
    # system message so we skip `format_system_message()`.
    from .build import _init_strands

    for qual_path, node in _labelled_tree(root):
        if _is_default_forward(node) and not node._children:
            _init_strands(node, cached_prompt=prompts.get(qual_path))

    object.__setattr__(root, "_built", True)
    for _, node in _labelled_tree(root):
        object.__setattr__(node, "_built", True)

    return root


__all__ = ["freeze_agent", "thaw_agent"]
