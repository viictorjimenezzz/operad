"""Freeze / thaw a built ``Agent`` to a single JSON file.

Freeze captures the three pieces of a compiled agent that are expensive
to recreate: the declared state (via ``AgentState``), the computation
graph (via ``to_json``), and each default-forward leaf's rendered system
message. Custom-forward agents (composites like ``Sequential``,
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
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from ..utils.errors import BuildError
from .agent import Agent, _labelled_tree, _system_to_str
from .agent import Example
from .view import from_json, to_json
from .output import OPERAD_VERSION_HASH, PYTHON_VERSION_HASH
from .state import AgentState

if TYPE_CHECKING:
    from ..optim.optimizers.optimizer import Optimizer


_KNOWN_AGENT_ATTRS: frozenset[str] = frozenset(
    {
        "role",
        "task",
        "style",
        "context",
        "name",
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

    For default-forward leaves we return ``{}``; their ``_runner`` is
    rebuilt by ``_init_runner`` on thaw.
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


def _state_from_frozen(state_dict: dict) -> AgentState:
    """Reconstruct an AgentState from a frozen JSON dict.

    Uses model_construct for Configuration so the api_key presence validator
    does not fire on redacted (api_key=None) frozen configs.
    """
    from .config import Configuration

    from .config import IOConfig, Resilience, Runtime, Sampling

    cfg_dict = state_dict.get("config")
    if cfg_dict:
        cfg = Configuration.model_construct(
            **{
                **cfg_dict,
                "sampling": Sampling.model_construct(**cfg_dict.get("sampling", {})),
                "resilience": Resilience.model_construct(**cfg_dict.get("resilience", {})),
                "io": IOConfig.model_construct(**cfg_dict.get("io", {})),
                "runtime": Runtime.model_construct(**cfg_dict.get("runtime", {})),
            }
        )
    else:
        cfg = None
    children = {
        k: _state_from_frozen(v)
        for k, v in state_dict.get("children", {}).items()
    }
    return AgentState.model_construct(
        class_name=state_dict["class_name"],
        name=state_dict.get("name", state_dict.get("class_name", "")),
        role=state_dict.get("role", ""),
        task=state_dict.get("task", ""),
        style=state_dict.get("style", ""),
        context=state_dict.get("context", ""),
        rules=state_dict.get("rules", []),
        examples=state_dict.get("examples", []),
        config=cfg,
        input_type_name=state_dict.get("input_type_name", ""),
        output_type_name=state_dict.get("output_type_name", ""),
        children=children,
    )


def _redact_state(state: AgentState) -> AgentState:
    """Return a copy of `state` with every `config.api_key` zeroed."""
    from .config import Configuration

    cfg = state.config
    if cfg is not None and getattr(cfg, "api_key", None) is not None:
        # Use model_construct to bypass validators — the redacted copy is
        # intentionally missing the api_key (security scrub before serialisation)
        # and must not re-trigger the api_key presence check.
        cfg = Configuration.model_construct(**{**cfg.__dict__, "api_key": None})
    # Use model_construct so the redacted cfg (api_key=None) is not re-validated.
    return AgentState.model_construct(
        class_name=state.class_name,
        name=state.name,
        role=state.role,
        task=state.task,
        style=state.style,
        context=state.context,
        rules=list(state.rules),
        examples=[dict(e) for e in state.examples],
        config=cfg,
        input_type_name=state.input_type_name,
        output_type_name=state.output_type_name,
        children={k: _redact_state(v) for k, v in state.children.items()},
    )


def _serialize_optimizer_state(sd: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe view of `Optimizer.state_dict()`.

    Walks recursively: ``BaseModel`` leaves are ``.model_dump(mode="json")``,
    any ``"api_key"`` key is scrubbed to ``None``, and non-JSON-native
    values (callables, sets, custom classes, bytes, ...) raise a loud
    ``BuildError`` — silent drops would corrupt resume.

    Note: ``TextualGradientDescent._cache`` is intentionally not exposed
    by ``state_dict()`` and thus not scrubbed here; rewriters rebuild
    lazily post-thaw. If a subclass ever adds `RewriteAgent` instances
    to ``state_dict``, extend this walker before shipping that change.
    """

    def _walk(value: Any, path: str) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                if not isinstance(k, str):
                    raise BuildError(
                        "not_built",
                        f"cannot freeze optimizer state at {path}: "
                        f"dict key {k!r} is not a string",
                    )
                if k == "api_key":
                    out[k] = None
                    continue
                out[k] = _walk(v, f"{path}.{k}")
            return out
        if isinstance(value, (list, tuple)):
            return [_walk(v, f"{path}[{i}]") for i, v in enumerate(value)]
        raise BuildError(
            "not_built",
            f"cannot freeze optimizer state at {path}: value of type "
            f"{type(value).__name__} is not JSON-serializable",
        )

    result = _walk(sd, "optimizer_state")
    if not isinstance(result, dict):
        raise BuildError(
            "not_built",
            f"optimizer.state_dict() must return a dict, got {type(sd).__name__}",
        )
    return result


def _deserialize_optimizer_state(data: Any) -> dict[str, Any] | None:
    """Rehydrate optimizer state for ``Optimizer.load_state_dict``.

    The only typed Pydantic leaf in the base-class ``state_dict`` is
    ``param_groups[i].constraint_override``; we rehydrate that via the
    ``ParameterConstraint`` discriminated union so the reloaded
    optimizer's ``state_dict()`` matches the original. Everything else
    is plain dicts/lists/primitives.
    """
    if data is None:
        return None
    if not isinstance(data, dict):
        raise BuildError(
            "not_built",
            f"optimizer_state must be a dict, got {type(data).__name__}",
        )

    from pydantic import TypeAdapter

    from ..optim.parameter import ParameterConstraint

    adapter: TypeAdapter[Any] = TypeAdapter(ParameterConstraint | None)

    groups = data.get("param_groups")
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, dict):
                continue
            co = group.get("constraint_override")
            if co is not None:
                group["constraint_override"] = adapter.validate_python(co)

    return data


def freeze_agent(
    agent: Agent,
    path: str | Path,
    *,
    optimizer: "Optimizer | None" = None,
) -> None:
    """Persist a built `agent` to `path` as a single JSON file.

    See module docstring for the format and v1 limitations.

    If `optimizer` is provided, its `state_dict()` is captured under an
    ``"optimizer_state"`` key for resume via :func:`thaw_pair`.
    """
    if not agent._built:
        raise BuildError(
            "not_built",
            f"cannot freeze {agent.name}: call .build() first",
            agent=agent.name,
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

    payload: dict[str, Any] = {
        "operad_version_hash": OPERAD_VERSION_HASH,
        "python_version_hash": PYTHON_VERSION_HASH,
        "agent_class": _qualified_class_name(type(agent)),
        "class_map": class_map,
        "state": state.model_dump(mode="json"),
        "graph": graph_json,
        "prompts": prompts,
        "routing": routing,
    }

    if optimizer is not None:
        payload["optimizer_state"] = _serialize_optimizer_state(
            optimizer.state_dict()
        )

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
    object.__setattr__(obj, "_runner", None)
    object.__setattr__(obj, "_requires_grad_overrides", {})
    object.__setattr__(obj, "_configuration_constraint", None)
    object.__setattr__(obj, "_forward_pre_hooks", [])
    object.__setattr__(obj, "_forward_hooks", [])
    object.__setattr__(obj, "_backward_hooks", [])
    obj.input = io[0]  # type: ignore[assignment]
    obj.output = io[1]  # type: ignore[assignment]
    obj.name = state.name or cls.__name__
    obj.role = state.role
    obj.task = state.task
    obj.style = state.style
    obj.context = state.context
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


def _thaw_from_data(data: dict[str, Any]) -> Agent:
    """Reconstruct a built Agent from an already-parsed frozen payload."""
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

    root_state = _state_from_frozen(data["state"])
    root_path = root_state.name or _resolve_class(data["agent_class"]).__name__
    root = _reconstruct(root_state, root_path, class_map, io_map)

    _restore_extra(root, root_path, routing)

    if graph_json is not None:
        object.__setattr__(root, "_graph", from_json(graph_json))

    # Construct the runner for every default-forward leaf, using the
    # cached system message so we skip `format_system_message()`.
    from .build import _init_runner

    for qual_path, node in _labelled_tree(root):
        if _is_default_forward(node) and not node._children:
            _init_runner(node, cached_prompt=prompts.get(qual_path))

    object.__setattr__(root, "_built", True)
    for _, node in _labelled_tree(root):
        object.__setattr__(node, "_built", True)

    return root


def thaw_agent(path: str | Path) -> Agent:
    """Reconstitute a built agent previously written with `freeze_agent`.

    Any persisted optimizer state is silently ignored; use
    :func:`thaw_pair` to recover it for resume.
    """
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return _thaw_from_data(data)


def thaw_pair(path: str | Path) -> tuple[Agent, dict[str, Any] | None]:
    """Thaw an agent and recover any persisted optimizer state.

    Returns ``(agent, optimizer_state)``. ``optimizer_state`` is
    ``None`` when the artefact was written without ``optimizer=...``.
    Pass the dict to ``optimizer.load_state_dict(...)`` to resume
    training.
    """
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    agent = _thaw_from_data(data)
    opt_state = _deserialize_optimizer_state(data.get("optimizer_state"))
    return agent, opt_state


__all__ = ["freeze_agent", "thaw_agent", "thaw_pair"]
