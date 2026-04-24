"""`freeze_agent(..., optimizer=...)` + `thaw_pair` round trip."""

from __future__ import annotations

import json
from typing import Any

import pytest

from operad import BuildError, Configuration
from operad.core.freeze import freeze_agent, thaw_agent, thaw_pair
from operad.optim.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import NumericConstraint, Parameter

from ..conftest import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


class _StubOpt(Optimizer):
    """Minimal concrete Optimizer for serialization round-trip tests."""

    def __init__(
        self, params: Any, *, lr: float = 1.0, momentum: float = 0.0
    ) -> None:
        super().__init__(params, defaults={"lr": lr, "momentum": momentum})

    async def step(self) -> None:  # pragma: no cover — not exercised
        return None

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:  # pragma: no cover — not exercised
        return None


async def _built_leaf(cfg: Configuration) -> FakeLeaf:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="describe")
    leaf.role = "critic"
    leaf.mark_trainable(role=True)
    await leaf.abuild()
    return leaf


async def test_freeze_then_thaw_pair_round_trips_optimizer(
    cfg: Configuration, tmp_path: Any
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOpt(list(leaf.parameters()), lr=0.5, momentum=0.1)

    # Non-trivial optimizer state so equality is meaningful.
    for p in opt.param_groups[0].params:
        p.momentum_state = {"running_summary": "seen-two-batches"}
        opt.state[p.path] = {"step_count": 3}

    path = tmp_path / "agent.json"
    freeze_agent(leaf, path, optimizer=opt)

    reloaded, opt_state = thaw_pair(path)
    assert opt_state is not None
    assert reloaded.hash_content == leaf.hash_content

    fresh = _StubOpt(list(reloaded.parameters()), lr=0.5, momentum=0.1)
    fresh.load_state_dict(opt_state)

    assert fresh.state_dict() == opt.state_dict()


async def test_freeze_scrubs_api_key_in_optimizer_extras(
    cfg: Configuration, tmp_path: Any
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOpt(list(leaf.parameters()))
    opt.param_groups[0].extras["api_key"] = "secret-999"

    path = tmp_path / "agent.json"
    freeze_agent(leaf, path, optimizer=opt)

    raw = path.read_text(encoding="utf-8")
    assert "secret-999" not in raw

    # Live optimizer is untouched.
    assert opt.param_groups[0].extras["api_key"] == "secret-999"


async def test_freeze_rejects_non_json_value_in_optimizer_state(
    cfg: Configuration, tmp_path: Any
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOpt(list(leaf.parameters()))
    opt.param_groups[0].extras["factory"] = lambda: 1  # not JSON-native

    with pytest.raises(BuildError) as exc:
        freeze_agent(leaf, tmp_path / "agent.json", optimizer=opt)
    assert exc.value.reason == "not_built"
    assert "JSON" in str(exc.value) or "optimizer_state" in str(exc.value)


async def test_constraint_override_round_trips_as_pydantic(
    cfg: Configuration, tmp_path: Any
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOpt(list(leaf.parameters()))
    opt.param_groups[0].constraint_override = NumericConstraint(
        min=0.0, max=1.0
    )

    path = tmp_path / "agent.json"
    freeze_agent(leaf, path, optimizer=opt)

    _, opt_state = thaw_pair(path)
    assert opt_state is not None

    fresh = _StubOpt(list((await _built_leaf(cfg)).parameters()))
    fresh.load_state_dict(opt_state)

    reloaded_co = fresh.param_groups[0].constraint_override
    assert isinstance(reloaded_co, NumericConstraint)
    assert reloaded_co.min == 0.0
    assert reloaded_co.max == 1.0


async def test_thaw_pair_returns_none_when_no_optimizer_persisted(
    cfg: Configuration, tmp_path: Any
) -> None:
    leaf = await _built_leaf(cfg)
    path = tmp_path / "agent.json"
    freeze_agent(leaf, path)  # no optimizer kwarg

    agent, opt_state = thaw_pair(path)
    assert opt_state is None
    assert agent.hash_content == leaf.hash_content


async def test_thaw_agent_ignores_persisted_optimizer_state(
    cfg: Configuration, tmp_path: Any
) -> None:
    leaf = await _built_leaf(cfg)
    opt = _StubOpt(list(leaf.parameters()))
    path = tmp_path / "agent.json"
    freeze_agent(leaf, path, optimizer=opt)

    # Backward compat: classic thaw_agent still works, drops opt state.
    reloaded = thaw_agent(path)
    assert reloaded.hash_content == leaf.hash_content

    # Sanity: the JSON file really does carry optimizer_state.
    assert "optimizer_state" in json.loads(path.read_text(encoding="utf-8"))
