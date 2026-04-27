"""Offline tests for `operad.optim.schedulers.lr` — PyTorch-style LR schedulers.

Each scheduler is exercised over a 10-epoch run against a `StubOptimizer`
(minimal `Optimizer` subclass) to verify formulas, state_dict round-trip,
per-param-group independence, and the "no clamp" contract.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter, TextParameter
from operad.optim.schedulers.lr import (
    ChainedScheduler,
    ConstantLR,
    CosineExplorationLR,
    ExponentialLR,
    LRScheduler,
    MultiStepLR,
    ReduceLROnPlateau,
    SequentialLR,
    StepLR,
    WarmupLR,
)
from tests._helpers.fake_leaf import A, B, FakeLeaf


class StubOptimizer(Optimizer):
    """Minimal concrete optimizer for scheduler tests."""

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


def _run(opt: StubOptimizer, sched: LRScheduler, n: int) -> list[float]:
    lrs: list[float] = []
    for _ in range(n):
        sched.step()
        lrs.append(opt.param_groups[0].lr)
    return lrs


def test_constant_lr_never_changes(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 0.7})
    sched = ConstantLR(opt)

    assert _run(opt, sched, 10) == [0.7] * 10


def test_step_lr_schedule(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    sched = StepLR(opt, step_size=3, gamma=0.5)

    lrs = _run(opt, sched, 10)
    expected = [1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.25, 0.25, 0.25, 0.125]
    assert lrs == pytest.approx(expected)


def test_step_lr_rejects_zero_step_size(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    with pytest.raises(ValueError, match="step_size"):
        StepLR(opt, step_size=0)


def test_multistep_lr_schedule(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    sched = MultiStepLR(opt, milestones=[2, 5], gamma=0.5)

    lrs = _run(opt, sched, 8)
    # milestones at last_epoch 2, 5 -> drop to 0.5 at step 3, to 0.25 at step 6
    expected = [1.0, 1.0, 0.5, 0.5, 0.5, 0.25, 0.25, 0.25]
    assert lrs == pytest.approx(expected)


def test_exponential_lr_schedule(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    sched = ExponentialLR(opt, gamma=0.9)

    lrs = _run(opt, sched, 5)
    expected = [0.9 ** i for i in range(5)]
    assert lrs == pytest.approx(expected)


def test_cosine_endpoints(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    sched = CosineExplorationLR(opt, T_max=10, eta_min=0.1)

    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(1.0)

    for _ in range(10):
        sched.step()
    assert opt.param_groups[0].lr == pytest.approx(0.1)


def test_cosine_rejects_zero_tmax(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    with pytest.raises(ValueError, match="T_max"):
        CosineExplorationLR(opt, T_max=0)


def test_warmup_monotonic(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 0.2})
    sched = WarmupLR(opt, warmup_epochs=3, final_lr=1.0)

    lrs = _run(opt, sched, 5)
    expected = [1.0 / 3.0, 2.0 / 3.0, 1.0, 1.0, 1.0]
    assert lrs == pytest.approx(expected)
    for a, b in zip(lrs[:3], lrs[1:3]):
        assert a < b


def test_reduce_lr_on_plateau_triggers(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    sched = ReduceLROnPlateau(opt, mode="min", factor=0.5, patience=1, threshold=1e-4)

    sched.step(1.0)
    assert opt.param_groups[0].lr == pytest.approx(1.0)
    sched.step(1.0)
    assert opt.param_groups[0].lr == pytest.approx(1.0)
    sched.step(1.0)
    assert opt.param_groups[0].lr == pytest.approx(0.5)


def test_reduce_lr_on_plateau_improvement_resets(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    sched = ReduceLROnPlateau(opt, mode="min", factor=0.5, patience=1, threshold=1e-4)

    sched.step(1.0)
    sched.step(1.0)
    sched.step(0.5)
    sched.step(0.5)
    assert opt.param_groups[0].lr == pytest.approx(1.0)


def test_state_dict_round_trip_step_lr(cfg: Any) -> None:
    params_a = _make_params(cfg, ["role"])
    opt_a = StubOptimizer(params_a, defaults={"lr": 1.0})
    sched_a = StepLR(opt_a, step_size=2, gamma=0.5)
    for _ in range(4):
        sched_a.step()
    sd = sched_a.state_dict()

    params_b = _make_params(cfg, ["role"])
    opt_b = StubOptimizer(params_b, defaults={"lr": 1.0})
    sched_b = StepLR(opt_b, step_size=2, gamma=0.5)
    sched_b.load_state_dict(sd)

    assert sched_b.last_epoch == sched_a.last_epoch
    assert sched_b.base_lrs == sched_a.base_lrs

    sched_a.step()
    sched_b.step()
    assert opt_b.param_groups[0].lr == pytest.approx(opt_a.param_groups[0].lr)


def test_state_dict_round_trip_plateau(cfg: Any) -> None:
    params_a = _make_params(cfg, ["role"])
    opt_a = StubOptimizer(params_a, defaults={"lr": 1.0})
    sched_a = ReduceLROnPlateau(opt_a, mode="min", factor=0.5, patience=2)
    for _ in range(3):
        sched_a.step(1.0)
    sd = sched_a.state_dict()

    params_b = _make_params(cfg, ["role"])
    opt_b = StubOptimizer(params_b, defaults={"lr": 1.0})
    sched_b = ReduceLROnPlateau(opt_b, mode="min", factor=0.5, patience=2)
    sched_b.load_state_dict(sd)

    assert sched_b.last_epoch == sched_a.last_epoch
    assert sched_b.best == sched_a.best
    assert sched_b.num_bad_epochs == sched_a.num_bad_epochs


def test_chained_scheduler_applies_all(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    const = ConstantLR(opt)
    expo = ExponentialLR(opt, gamma=0.5)
    chain = ChainedScheduler([const, expo])

    chain.step()
    chain.step()

    assert const.last_epoch == 1
    assert expo.last_epoch == 1
    assert opt.param_groups[0].lr == pytest.approx(0.5)


def test_sequential_lr_switches_at_milestone(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    warmup = WarmupLR(opt, warmup_epochs=3, final_lr=1.0)
    expo = ExponentialLR(opt, gamma=0.9)
    sched = SequentialLR(opt, schedulers=[warmup, expo], milestones=[3])

    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(1.0 / 3.0)
    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(2.0 / 3.0)
    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(1.0)
    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(1.0)
    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(0.9)
    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(0.81)

    assert warmup.last_epoch == 2
    assert expo.last_epoch == 2


def test_sequential_lr_validates_milestone_count(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    s1 = ConstantLR(opt)
    s2 = ConstantLR(opt)
    with pytest.raises(ValueError, match="milestones"):
        SequentialLR(opt, schedulers=[s1, s2], milestones=[1, 2])


def test_per_param_group_independence(cfg: Any) -> None:
    params_a = _make_params(cfg, ["role"])
    params_b = _make_params(cfg, ["task"])
    opt = StubOptimizer(
        [
            {"params": params_a, "lr": 1.0},
            {"params": params_b, "lr": 0.2},
        ]
    )
    sched = ExponentialLR(opt, gamma=0.5)

    sched.step()
    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(0.5)
    assert opt.param_groups[1].lr == pytest.approx(0.1)


def test_scheduler_does_not_clamp(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 0.6})
    sched = ExponentialLR(opt, gamma=2.0)

    sched.step()
    sched.step()
    assert opt.param_groups[0].lr == pytest.approx(1.2)


def test_cosine_full_curve_matches_formula(cfg: Any) -> None:
    params = _make_params(cfg, ["role"])
    opt = StubOptimizer(params, defaults={"lr": 1.0})
    T_max = 4
    eta_min = 0.0
    sched = CosineExplorationLR(opt, T_max=T_max, eta_min=eta_min)

    for expected_epoch in range(T_max + 1):
        sched.step()
        t = min(expected_epoch, T_max)
        expected = eta_min + (1.0 - eta_min) * 0.5 * (1.0 + math.cos(math.pi * t / T_max))
        assert opt.param_groups[0].lr == pytest.approx(expected)
