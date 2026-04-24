"""Offline tests for `operad.optim.optimizer` — `Optimizer` base class.

Uses a minimal `StubOptimizer` that only implements the abstract hooks,
so these tests focus on the base-class surface: parameter-group
normalization, `zero_grad`, `named_parameters`, `state_dict` round-trip,
and `add_param_group`.
"""

from __future__ import annotations

from typing import Any

import pytest

from operad.optim import (
    Optimizer,
    ParamGroup,
    Parameter,
    TextParameter,
    TextualGradient,
)
from tests._helpers.fake_leaf import A, B, FakeLeaf


class StubOptimizer(Optimizer):
    """Minimal concrete optimizer for base-class tests."""

    async def step(self) -> None:
        return None

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        return None


_LEAF_POOL: list[Any] = []


def _make_params(cfg: Any, paths: list[str]) -> list[TextParameter]:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    _LEAF_POOL.append(leaf)
    out: list[TextParameter] = []
    for i, path in enumerate(paths):
        if path == "role":
            leaf.role = f"role-{i}"
        elif path == "task":
            leaf.task = f"task-{i}"
        out.append(TextParameter.from_agent(leaf, path, path))  # type: ignore[arg-type]
    return out


def test_plain_list_constructor_normalizes_to_single_group(cfg: Any) -> None:
    params = _make_params(cfg, ["role", "task"])
    opt = StubOptimizer(params, defaults={"lr": 0.5})

    assert len(opt.param_groups) == 1
    group = opt.param_groups[0]
    assert group.lr == 0.5
    assert group.params == params


def test_dict_groups_carry_independent_lr(cfg: Any) -> None:
    params_a = _make_params(cfg, ["role"])
    params_b = _make_params(cfg, ["task"])
    opt = StubOptimizer(
        [
            {"params": params_a, "lr": 2.0},
            {"params": params_b, "lr": 0.3},
        ]
    )

    assert len(opt.param_groups) == 2
    assert opt.param_groups[0].lr == 2.0
    assert opt.param_groups[1].lr == 0.3
    assert opt.param_groups[0].params == params_a
    assert opt.param_groups[1].params == params_b


def test_dict_groups_extra_keys_land_in_extras(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    sentinel = object()
    opt = StubOptimizer(
        [{"params": params, "lr": 1.0, "rewriter_factory": sentinel}]
    )

    assert opt.param_groups[0].extras["rewriter_factory"] is sentinel


def test_mixing_parameters_and_dicts_raises(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    with pytest.raises(TypeError, match="cannot mix"):
        StubOptimizer([params[0], {"params": params}])  # type: ignore[list-item]


def test_empty_iterable_raises(cfg: Any) -> None:
    with pytest.raises(ValueError, match="empty parameter iterable"):
        StubOptimizer([])


def test_group_dict_missing_params_raises(cfg: Any) -> None:
    with pytest.raises(KeyError, match="'params'"):
        StubOptimizer([{"lr": 1.0}])


def test_group_dict_non_parameter_entry_raises(cfg: Any) -> None:
    with pytest.raises(TypeError, match="non-Parameter entry"):
        StubOptimizer([{"params": ["not-a-parameter"]}])


def test_zero_grad_clears_grads_across_groups(cfg: Any) -> None:
    params_a = _make_params(cfg, ["role"])
    params_b = _make_params(cfg, ["task"])
    for p in params_a + params_b:
        p.grad = TextualGradient(message="critique", severity=1.0)

    opt = StubOptimizer(
        [
            {"params": params_a, "lr": 1.0},
            {"params": params_b, "lr": 0.5},
        ]
    )
    opt.zero_grad()

    for p in params_a + params_b:
        assert p.grad is None


def test_named_parameters_yields_in_group_order(cfg: Any) -> None:
    params_a = _make_params(cfg, ["role"])
    params_b = _make_params(cfg, ["task"])
    opt = StubOptimizer(
        [
            {"params": params_a, "lr": 1.0},
            {"params": params_b, "lr": 0.5},
        ]
    )

    names = [name for name, _ in opt.named_parameters()]
    assert names == ["role", "task"]


def test_add_param_group_appends(cfg: Any) -> None:
    params_a = _make_params(cfg, ["role"])
    params_b = _make_params(cfg, ["task"])
    opt = StubOptimizer(params_a, defaults={"lr": 1.0})
    opt.add_param_group({"params": params_b, "lr": 0.25})

    assert len(opt.param_groups) == 2
    assert opt.param_groups[1].lr == 0.25
    assert opt.param_groups[1].params == params_b


def test_state_dict_round_trip_preserves_momentum_state(cfg: Any) -> None:
    params = _make_params(cfg, ["role", "task"])
    params[0].momentum_state = {"m": 0.5}
    params[1].momentum_state = {"m": 0.25}

    opt = StubOptimizer(params, defaults={"lr": 1.5})
    opt.state["role"] = {"step_count": 3}
    sd = opt.state_dict()

    params[0].momentum_state = {}
    params[1].momentum_state = {}
    opt.state.clear()
    opt.param_groups[0].lr = 99.0

    opt.load_state_dict(sd)

    assert params[0].momentum_state == {"m": 0.5}
    assert params[1].momentum_state == {"m": 0.25}
    assert opt.state["role"] == {"step_count": 3}
    assert opt.param_groups[0].lr == 1.5


def test_load_state_dict_rejects_mismatched_group_count(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params)

    with pytest.raises(ValueError, match="param groups"):
        opt.load_state_dict({"state": {}, "param_groups": [{}, {}]})
