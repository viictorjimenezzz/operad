from __future__ import annotations

"""Apply one targeted prompt rewrite.

Owner: 4-2-apply-fix.
"""

import contextlib
import difflib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from operad import Agent
import operad.optim.backprop
from operad.optim.backprop.grad import BackpropAgent, ParameterGradAgent
from operad.optim.optimizers.tgd import TextualGradientDescent
from operad.optim.parameter import Parameter
from operad.utils.cassette import cassette_context
from pydantic import BaseModel, ConfigDict
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from apps_uthereal.feedback.loss import (
    HumanFeedbackLoss,
    SPECIAL_TARGETS,
    UnactionableFeedback,
)
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.leaves._common import dump_yaml, load_yaml, split_closure_from_task
from apps_uthereal.leaves.registry import LEAF_REGISTRY, LEAF_STEP_NAMES
from apps_uthereal.tiers import TIER_THINKING_LOW, tier_to_config
from apps_uthereal.workflow.runner import ArtemisRunner


TRAINABLE_FIELDS: tuple[str, ...] = ("role", "task", "rules")


class FixReport(BaseModel):
    """Summary of a targeted prompt rewrite."""

    target_path: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    diff_text: str
    yaml_path: Path
    yaml_dry_run: bool
    severity: float

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def apply_fix(
    *,
    runner: ArtemisRunner,
    artemis_input: Any,
    feedback: HumanFeedback,
    target_path: str,
    yaml_root: Path,
    dry_run: bool = False,
    lr: float = 1.0,
    llm_cassette_path: Path | None = None,
    gradient_agents: tuple[BackpropAgent, ParameterGradAgent] | None = None,
) -> FixReport:
    """Run targeted backward propagation, rewrite one leaf, and dump YAML.

    The caller owns building ``runner`` before calling this function.

    ``llm_cassette_path`` scopes a replay-mode cassette around the runner pass
    only. The gradient-propagation and rewriter LLM calls run live, since the
    original cassette only contains the leaf calls.

    ``gradient_agents`` lets callers (mostly tests) inject pre-built propagator
    / parameter-grad agents instead of constructing live Gemini-backed ones.
    """

    if target_path in SPECIAL_TARGETS:
        raise UnactionableFeedback(
            reason=target_path,
            message=(
                f"Feedback target {target_path!r} cannot be turned into "
                "a leaf-targeted gradient."
            ),
        )

    target_leaf = _get_submodule(runner, target_path)
    yaml_path = _yaml_path_for_step(yaml_root, target_path)

    before_runner_state = _flatten_state(runner.state())
    before_leaf_state = _state_dict(target_leaf)
    override_snapshot = _snapshot_requires_grad_overrides(runner)

    try:
        parameters = _scope_target_parameters(
            runner,
            target_leaf=target_leaf,
            target_path=target_path,
        )

        runner_cassette = (
            cassette_context(llm_cassette_path, mode="replay")
            if llm_cassette_path is not None
            else contextlib.nullcontext()
        )
        async with operad.optim.backprop.tape() as taped:
            with runner_cassette:
                answer, _trace = await runner.run_with_trace(artemis_input)

        feedback_for_loss = feedback.model_copy(update={"target_path": target_path})
        _score, grad = await HumanFeedbackLoss().compute(answer, feedback_for_loss)
        gradient_config = tier_to_config(
            TIER_THINKING_LOW,
            overrides={"sampling.max_tokens": 8192},
        )
        if gradient_agents is None:
            propagator = await BackpropAgent(config=gradient_config).abuild()
            param_grad = await ParameterGradAgent(config=gradient_config).abuild()
        else:
            propagator, param_grad = gradient_agents

        await taped.backward(
            grad,
            parameters=parameters,
            propagator_factory=lambda: propagator,
            parameter_grad_factory=lambda _kind: param_grad,
        )
        await TextualGradientDescent(parameters, lr=lr, config=gradient_config).step()

        _assert_only_target_changed(
            runner,
            target_path,
            before_runner_state,
        )
        after_leaf_state = _state_dict(target_leaf)
        diff_text = _diff_trainable_fields(
            target_path,
            before_leaf_state,
            after_leaf_state,
        )

        if not dry_run:
            dump_yaml(target_leaf, yaml_path, source_path=yaml_path)
            reloaded = load_yaml(yaml_path, leaf_cls=_leaf_cls_for_step(target_path))
            if reloaded.hash_content != target_leaf.hash_content:
                _rewrite_trainable_yaml_fields(target_leaf, yaml_path)
                reloaded = load_yaml(
                    yaml_path,
                    leaf_cls=_leaf_cls_for_step(target_path),
                )
            assert (
                reloaded.hash_content == target_leaf.hash_content
            ), "dumped YAML does not round-trip to the in-memory leaf"

        return FixReport(
            target_path=target_path,
            before_state=before_leaf_state,
            after_state=after_leaf_state,
            diff_text=diff_text,
            yaml_path=yaml_path,
            yaml_dry_run=dry_run,
            severity=feedback_for_loss.severity,
        )
    finally:
        if dry_run:
            _restore_trainable_fields(target_leaf, before_leaf_state)
        _restore_requires_grad_overrides(override_snapshot)


def _assert_only_target_changed(
    runner: Agent[Any, Any],
    target_path: str,
    before_state: dict[str, Any],
) -> None:
    """Assert that only state keys under ``target_path`` changed."""

    after_state = _flatten_state(runner.state())
    target_prefix = f"{target_path}."
    for path, before in before_state.items():
        if path.startswith(target_prefix):
            continue
        assert after_state.get(path) == before, f"unexpected change at {path}"


def _yaml_path_for_step(yaml_root: Path, step_name: str) -> Path:
    """Map a runner step name to its source YAML path under ``yaml_root``."""

    for relative_path, registered_step in LEAF_STEP_NAMES.items():
        if registered_step == step_name:
            return Path(yaml_root) / relative_path
    raise KeyError(f"unknown leaf step {step_name!r}")


def _get_submodule(root: Agent[Any, Any], path: str) -> Agent[Any, Any]:
    current: Any = root
    for segment in path.split("."):
        if not segment:
            raise KeyError(f"empty path segment in {path!r}")
        current = getattr(current, segment)
        if not isinstance(current, Agent):
            raise KeyError(f"path {path!r} does not resolve to an Agent")
    return current


def _scope_target_parameters(
    runner: Agent[Any, Any],
    *,
    target_leaf: Agent[Any, Any],
    target_path: str,
) -> list[Parameter[Any]]:
    _freeze_all_parameter_overrides(runner)
    runner.unfreeze_parameters(
        **{f"{target_path}.{field}": True for field in TRAINABLE_FIELDS}
    )

    allowed_paths = {f"{target_path}.{field}" for field in TRAINABLE_FIELDS}
    unexpected = [
        path
        for path, parameter in runner.named_parameters()
        if parameter.requires_grad and path not in allowed_paths
    ]
    assert not unexpected, f"unexpected trainable parameters: {unexpected}"

    parameters = [
        parameter
        for path, parameter in target_leaf.named_parameters(recurse=False)
        if path in TRAINABLE_FIELDS and parameter.requires_grad
    ]
    assert len(parameters) == len(TRAINABLE_FIELDS), (
        "target leaf did not expose all trainable fields: "
        f"{[parameter.path for parameter in parameters]}"
    )
    return parameters


def _freeze_all_parameter_overrides(root: Agent[Any, Any]) -> None:
    for path, _parameter in root.named_parameters():
        owner, local_path = _parameter_owner(root, path)
        getattr(owner, "_requires_grad_overrides")[local_path] = False


def _parameter_owner(
    root: Agent[Any, Any],
    parameter_path: str,
) -> tuple[Agent[Any, Any], str]:
    current = root
    segments = parameter_path.split(".")
    while segments and isinstance(getattr(current, segments[0], None), Agent):
        current = getattr(current, segments.pop(0))
    return current, ".".join(segments)


def _snapshot_requires_grad_overrides(
    root: Agent[Any, Any],
) -> list[tuple[Agent[Any, Any], dict[str, bool]]]:
    return [
        (agent, dict(getattr(agent, "_requires_grad_overrides")))
        for agent in _iter_agents(root)
    ]


def _restore_requires_grad_overrides(
    snapshot: Iterable[tuple[Agent[Any, Any], dict[str, bool]]],
) -> None:
    for agent, overrides in snapshot:
        current = getattr(agent, "_requires_grad_overrides")
        current.clear()
        current.update(overrides)


def _iter_agents(root: Agent[Any, Any]) -> Iterable[Agent[Any, Any]]:
    yield root
    for child in getattr(root, "_children", {}).values():
        yield from _iter_agents(child)


def _state_dict(agent: Agent[Any, Any]) -> dict[str, Any]:
    return agent.state().model_dump(mode="json")


def _restore_trainable_fields(
    agent: Agent[Any, Any],
    state: dict[str, Any],
) -> None:
    agent.role = str(state["role"])
    agent.task = str(state["task"])
    agent.rules = list(state["rules"])


def _flatten_state(state: Any, *, prefix: str = "") -> dict[str, Any]:
    data = state.model_dump(mode="json") if hasattr(state, "model_dump") else dict(state)
    flattened: dict[str, Any] = {}
    children = data.get("children", {})
    for key, value in data.items():
        if key == "children":
            continue
        flattened[f"{prefix}{key}"] = value
    for child_name, child_state in children.items():
        flattened.update(
            _flatten_state(child_state, prefix=f"{prefix}{child_name}.")
        )
    return flattened


def _diff_trainable_fields(
    target_path: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
) -> str:
    before = _render_trainable_fields(before_state)
    after = _render_trainable_fields(after_state)
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"{target_path}:before",
            tofile=f"{target_path}:after",
            n=3,
        )
    )


def _render_trainable_fields(state: dict[str, Any]) -> str:
    lines: list[str] = []
    for field in TRAINABLE_FIELDS:
        lines.append(f"## {field}")
        value = state.get(field, "")
        if field == "rules":
            lines.extend(str(rule) for rule in value or [])
        else:
            lines.extend(str(value).splitlines())
        lines.append("")
    return "\n".join(lines)


def _leaf_cls_for_step(step_name: str) -> type[Agent[Any, Any]]:
    for relative_path, registered_step in LEAF_STEP_NAMES.items():
        if registered_step == step_name:
            return LEAF_REGISTRY[relative_path]
    raise KeyError(f"unknown leaf step {step_name!r}")


def _rewrite_trainable_yaml_fields(agent: Agent[Any, Any], yaml_path: Path) -> None:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    data = yaml.load(yaml_path.read_text(encoding="utf-8"))
    prompt = data.setdefault("prompt", {})
    task_body, closure = split_closure_from_task(str(agent.task))
    prompt["role"] = str(agent.role)
    prompt["task"] = task_body
    prompt["closure"] = closure
    prompt["rules"] = CommentedSeq([str(rule) for rule in agent.rules])
    with yaml_path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


__all__ = [
    "FixReport",
    "TRAINABLE_FIELDS",
    "apply_fix",
    "_assert_only_target_changed",
    "_yaml_path_for_step",
]
