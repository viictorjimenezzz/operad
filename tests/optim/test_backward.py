"""Offline tests for `operad.optim.backward`.

Every LLM call is stubbed via `BackpropAgent` / `ParameterGradAgent`
subclasses with overridden `forward`. The tests cover the full
backward walk (leaf, Sequential, Parallel, Router), null-gradient
short-circuit, backward hooks, custom split rules, error surfacing,
determinism, plus direct unit tests for each built-in split rule.
"""

from __future__ import annotations

import time
import weakref
from typing import Any, Literal

import pytest
from pydantic import BaseModel

from operad.core.flow import Parallel
from operad.core.flow import Router
from operad.core.flow import Sequential
from operad.agents.reasoning.components.router import RouteClassifier
from operad.agents.reasoning.schemas import Choice
from operad.core.agent import Agent
from operad.optim import (
    BackpropAgent,
    ParameterGradAgent,
    ParameterGradInput,
    ParameterGradOutput,
    PropagateInput,
    PropagateOutput,
    TextualGradient,
    backward,
    register_backward_rule,
    tape,
)
from operad.core.agent import _TRACER
from operad.optim.backward import (
    _RULES,
    _generic_composite_rule,
    _parallel_split,
    _pipeline_split,
    _router_split,
)
from operad.optim.tape import TapeEntry
from operad.runtime.observers import registry as obs_registry
from tests._helpers.fake_leaf import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_registry():
    obs_registry.clear()
    yield
    obs_registry.clear()


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubBackprop(BackpropAgent):
    def __init__(
        self,
        *,
        canned: PropagateOutput | None = None,
        config: Any = None,
    ) -> None:
        super().__init__(config=config)
        self.canned = canned or PropagateOutput(
            message="refined critique", severity=0.7
        )
        self.calls: list[PropagateInput] = []

    async def forward(self, x: PropagateInput) -> PropagateOutput:  # type: ignore[override]
        if _TRACER.get() is None:
            self.calls.append(x)
        return self.canned


class StubParamGrad(ParameterGradAgent):
    def __init__(
        self,
        *,
        canned: ParameterGradOutput | None = None,
        config: Any = None,
    ) -> None:
        super().__init__(config=config)
        self.canned = canned or ParameterGradOutput(
            message="param critique", severity=0.5
        )
        self.calls: list[ParameterGradInput] = []

    async def forward(self, x: ParameterGradInput) -> ParameterGradOutput:  # type: ignore[override]
        if _TRACER.get() is None:
            self.calls.append(x)
        return self.canned


async def _built_backprop(canned: PropagateOutput | None = None) -> StubBackprop:
    agent = StubBackprop(canned=canned)
    await agent.abuild()
    return agent


async def _built_param_grad(
    canned: ParameterGradOutput | None = None,
) -> StubParamGrad:
    agent = StubParamGrad(canned=canned)
    await agent.abuild()
    return agent


# ---------------------------------------------------------------------------
# 1. Leaf — every trainable parameter gets .grad
# ---------------------------------------------------------------------------


async def test_leaf_populates_grad_on_every_trainable_param(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 7})
    leaf.mark_trainable(role=True, task=True, rules=True)
    await leaf.abuild()

    params = list(leaf.parameters())

    async with tape() as t:
        await leaf(A(text="hi"))

    bp = await _built_backprop()
    pg = await _built_param_grad()
    loss = TextualGradient(message="be better", severity=1.0)
    await backward(
        t,
        loss,
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )

    trainable = [p for p in params if p.requires_grad]
    assert trainable
    for p in trainable:
        assert p.grad is not None, f"no grad on {p.path}"
        assert p.grad.message == "param critique"
        assert p.grad.severity == 0.5

    non_trainable = [p for p in params if not p.requires_grad]
    for p in non_trainable:
        assert p.grad is None


# ---------------------------------------------------------------------------
# 2. Sequential — both stages see propagate and get per-param grads
# ---------------------------------------------------------------------------


async def test_pipeline_propagates_through_each_stage(cfg) -> None:
    s0 = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    s1 = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})
    s0.mark_trainable(role=True)
    s1.mark_trainable(role=True)
    pipe = await Sequential(s0, s1, input=A, output=C).abuild()

    params = list(pipe.parameters())

    async with tape() as t:
        await pipe(A(text="go"))

    bp = await _built_backprop()
    pg = await _built_param_grad()
    loss = TextualGradient(message="global critique", severity=0.9)
    await backward(
        t,
        loss,
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )

    role_grads = {
        p._agent(): p.grad
        for p in params
        if p.requires_grad and p.path == "role"
    }
    assert role_grads.get(s0) is not None
    assert role_grads.get(s1) is not None
    # propagate fired at least 3 times: Sequential + stage_0 + stage_1.
    assert len(bp.calls) >= 3


# ---------------------------------------------------------------------------
# 3. Parallel — fan out the same grad to every branch
# ---------------------------------------------------------------------------


async def test_parallel_fan_out_same_grad_to_every_branch(cfg) -> None:
    a = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    b = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 2})
    for leaf in (a, b):
        leaf.mark_trainable(role=True)

    def _combine(results: dict[str, BaseModel]) -> C:
        return C(label="c")

    par = await Parallel(
        {"a": a, "b": b}, input=A, output=C, combine=_combine
    ).abuild()

    params = list(par.parameters())

    async with tape() as t:
        await par(A(text="x"))

    bp = await _built_backprop(
        canned=PropagateOutput(message="refined", severity=0.7)
    )
    pg = await _built_param_grad(
        canned=ParameterGradOutput(message="same", severity=0.5)
    )
    loss = TextualGradient(message="fix me", severity=1.0)
    await backward(
        t,
        loss,
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )

    role_grads = {
        p._agent(): p.grad
        for p in params
        if p.requires_grad and p.path == "role"
    }
    assert role_grads[a] is not None
    assert role_grads[b] is not None
    assert role_grads[a].message == role_grads[b].message
    assert role_grads[a].severity == role_grads[b].severity


# ---------------------------------------------------------------------------
# 4. Router — only the taken branch receives the grad
# ---------------------------------------------------------------------------


class _Label(Choice[Literal["a", "b"]]):
    pass


class _StubRouter(RouteClassifier):
    def __init__(self, *, label: str) -> None:
        super().__init__(config=None, input=A, output=_Label)
        self._label = label

    async def forward(self, x: Any) -> Any:  # type: ignore[override]
        return _Label.model_construct(label=self._label, reasoning="stub")


async def test_switch_taken_branch_only_gets_grad(cfg) -> None:
    branch_a = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    branch_b = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 2})
    for leaf in (branch_a, branch_b):
        leaf.mark_trainable(role=True)

    s = await Router(
        router=_StubRouter(label="a"),
        branches={"a": branch_a, "b": branch_b},
        input=A,
        output=B,
    ).abuild()

    params = list(s.parameters())

    async with tape() as t:
        await s(A(text="go"))

    bp = await _built_backprop()
    pg = await _built_param_grad()
    loss = TextualGradient(message="fix", severity=1.0)
    await backward(
        t,
        loss,
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )

    role_a = next(
        p for p in params
        if p.path == "role" and p._agent() is branch_a
    )
    role_b = next(
        p for p in params
        if p.path == "role" and p._agent() is branch_b
    )
    assert role_a.grad is not None
    assert role_b.grad is None


# ---------------------------------------------------------------------------
# 5. Null-gradient short-circuit
# ---------------------------------------------------------------------------


async def test_null_loss_leaves_all_grads_none(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.mark_trainable(role=True, task=True)
    await leaf.abuild()

    params = list(leaf.parameters())

    async with tape() as t:
        await leaf(A(text="hi"))

    bp = await _built_backprop()
    pg = await _built_param_grad()
    await backward(
        t,
        TextualGradient.null_gradient(),
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )

    for p in params:
        assert p.grad is None
    assert bp.calls == []
    assert pg.calls == []


# ---------------------------------------------------------------------------
# 6. Backward hooks fire with the propagated grad
# ---------------------------------------------------------------------------


async def test_register_backward_hook_fires_with_grad(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.mark_trainable(role=True)
    await leaf.abuild()

    params = list(leaf.parameters())

    seen: list[tuple[Any, TextualGradient]] = []

    def hook(agent: Any, grad: TextualGradient) -> None:
        seen.append((agent, grad))
        return None

    leaf.register_backward_hook(hook)

    async with tape() as t:
        await leaf(A(text="hi"))

    bp = await _built_backprop(
        canned=PropagateOutput(message="refined-X", severity=0.7)
    )
    pg = await _built_param_grad()
    await backward(
        t,
        TextualGradient(message="loss", severity=1.0),
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )

    assert len(seen) == 1
    hooked_agent, hooked_grad = seen[0]
    assert hooked_agent is leaf
    assert hooked_grad.message == "refined-X"


async def test_backward_hook_can_replace_grad(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.mark_trainable(role=True)
    await leaf.abuild()

    params = list(leaf.parameters())
    replacement = TextualGradient(message="replaced", severity=0.1)

    def hook(agent: Any, grad: TextualGradient) -> TextualGradient:
        return replacement

    leaf.register_backward_hook(hook)

    async with tape() as t:
        await leaf(A(text="hi"))

    bp = await _built_backprop()
    pg = await _built_param_grad()
    await backward(
        t,
        TextualGradient(message="loss", severity=1.0),
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )

    # The param-grad stub should have been called with the replaced grad
    # (severity 0.1, message "replaced") as the output_gradient.
    assert pg.calls
    assert pg.calls[0].output_gradient == "replaced"


# ---------------------------------------------------------------------------
# 7. Custom split rule overrides the built-in
# ---------------------------------------------------------------------------


async def test_register_backward_rule_overrides_builtin(cfg) -> None:
    s0 = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    s1 = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})
    s0.mark_trainable(role=True)
    s1.mark_trainable(role=True)
    pipe = await Sequential(s0, s1, input=A, output=C).abuild()

    params = list(pipe.parameters())

    async with tape() as t:
        await pipe(A(text="go"))

    def only_last(
        entry: TapeEntry,
        out_grad: TextualGradient,
        children: list[TapeEntry],
    ) -> dict[str, TextualGradient]:
        null = TextualGradient.null_gradient()
        return {
            ch.agent_path: (
                out_grad if ch.agent_path == children[-1].agent_path else null
            )
            for ch in children
        }

    original = _RULES.get(Sequential)
    register_backward_rule(Sequential, only_last)
    try:
        bp = await _built_backprop()
        pg = await _built_param_grad()
        await backward(
            t,
            TextualGradient(message="fix", severity=1.0),
            parameters=params,
            propagator_factory=lambda: bp,
            parameter_grad_factory=lambda kind: pg,
        )
    finally:
        if original is None:
            _RULES.pop(Sequential, None)
        else:
            _RULES[Sequential] = original

    role_s0 = next(
        p for p in params if p.path == "role" and p._agent() is s0
    )
    role_s1 = next(
        p for p in params if p.path == "role" and p._agent() is s1
    )
    assert role_s0.grad is None
    assert role_s1.grad is not None


# ---------------------------------------------------------------------------
# 8. Propagator error surfaces the node path
# ---------------------------------------------------------------------------


async def test_propagator_error_surfaces_path(cfg) -> None:
    class BrokenBackprop(BackpropAgent):
        async def forward(self, x: PropagateInput) -> PropagateOutput:  # type: ignore[override]
            if _TRACER.get() is not None:
                return PropagateOutput(message="trace", severity=0.0)
            raise RuntimeError("boom")

    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.mark_trainable(role=True)
    await leaf.abuild()

    params = list(leaf.parameters())

    async with tape() as t:
        await leaf(A(text="x"))

    br = BrokenBackprop()
    await br.abuild()
    pg = await _built_param_grad()
    with pytest.raises(RuntimeError, match=r"propagate failed at 'FakeLeaf'"):
        await backward(
            t,
            TextualGradient(message="x", severity=1.0),
            parameters=params,
            propagator_factory=lambda: br,
            parameter_grad_factory=lambda kind: pg,
        )


# ---------------------------------------------------------------------------
# 9. Determinism — same tape + same canned stubs => same grads
# ---------------------------------------------------------------------------


async def test_two_backward_runs_produce_identical_grads(cfg) -> None:
    s0 = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    s1 = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "ok"})
    s0.mark_trainable(role=True)
    s1.mark_trainable(role=True)
    pipe = await Sequential(s0, s1, input=A, output=C).abuild()

    params = list(pipe.parameters())

    async with tape() as t:
        await pipe(A(text="go"))

    loss = TextualGradient(message="global", severity=0.9)
    bp_canned = PropagateOutput(message="refined", severity=0.7)
    pg_canned = ParameterGradOutput(message="grad", severity=0.4)

    bp1 = await _built_backprop(bp_canned)
    pg1 = await _built_param_grad(pg_canned)
    await backward(
        t,
        loss,
        parameters=params,
        propagator_factory=lambda: bp1,
        parameter_grad_factory=lambda kind: pg1,
    )
    run1 = [
        (p.path, p.grad.model_dump()) if p.grad is not None else (p.path, None)
        for p in params
    ]

    for p in params:
        p.zero_grad()

    bp2 = await _built_backprop(bp_canned)
    pg2 = await _built_param_grad(pg_canned)
    await backward(
        t,
        loss,
        parameters=params,
        propagator_factory=lambda: bp2,
        parameter_grad_factory=lambda kind: pg2,
    )
    run2 = [
        (p.path, p.grad.model_dump()) if p.grad is not None else (p.path, None)
        for p in params
    ]

    assert run1 == run2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_backward_on_empty_tape_is_noop(cfg) -> None:
    from operad.optim.tape import Tape

    empty = Tape()
    bp = await _built_backprop()
    pg = await _built_param_grad()
    with pytest.warns(RuntimeWarning, match="empty tape"):
        await backward(
            empty,
            TextualGradient(message="x", severity=1.0),
            propagator_factory=lambda: bp,
            parameter_grad_factory=lambda kind: pg,
        )
    assert bp.calls == []
    assert pg.calls == []


async def test_tape_backward_convenience_method(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.mark_trainable(role=True)
    await leaf.abuild()

    params = list(leaf.parameters())

    async with tape() as t:
        await leaf(A(text="hi"))

    bp = await _built_backprop()
    pg = await _built_param_grad()
    await t.backward(
        TextualGradient(message="fix", severity=1.0),
        parameters=params,
        propagator_factory=lambda: bp,
        parameter_grad_factory=lambda kind: pg,
    )
    role = next(p for p in params if p.path == "role" and p.requires_grad)
    assert role.grad is not None


# ---------------------------------------------------------------------------
# Direct unit tests for split rules
# ---------------------------------------------------------------------------


def _mk_entry(path: str, *, output: BaseModel | None = None) -> TapeEntry:
    class _Dummy:
        pass

    d = _Dummy()
    return TapeEntry(
        run_id="r",
        agent_path=path,
        agent_ref=weakref.ref(d),
        input=A(text=""),
        output=output,
        rendered_prompt=None,
        started_at=time.monotonic(),
        finished_at=None,
        event_id=path,
        is_leaf=False,
    )


async def test_pipeline_split_gives_last_stage_full_grad() -> None:
    g = TextualGradient(message="fix", severity=0.9)
    children = [
        _mk_entry("Sequential.stage_0"),
        _mk_entry("Sequential.stage_1"),
    ]
    out = _pipeline_split(_mk_entry("Sequential"), g, children)
    assert out["Sequential.stage_1"].message == "fix"
    assert out["Sequential.stage_1"].severity == 0.9
    # Earlier stages get a copy (not the same instance).
    assert out["Sequential.stage_0"].message == "fix"


async def test_pipeline_split_with_single_child() -> None:
    g = TextualGradient(message="fix", severity=0.5)
    children = [_mk_entry("Sequential.stage_0")]
    out = _pipeline_split(_mk_entry("Sequential"), g, children)
    assert out["Sequential.stage_0"] is g  # last == only


async def test_pipeline_split_with_no_children() -> None:
    g = TextualGradient(message="fix", severity=0.5)
    assert _pipeline_split(_mk_entry("Sequential"), g, []) == {}


async def test_parallel_split_fans_out_uniformly() -> None:
    g = TextualGradient(message="fix", severity=0.4)
    children = [
        _mk_entry("Parallel.a"),
        _mk_entry("Parallel.b"),
        _mk_entry("Parallel.c"),
    ]
    out = _parallel_split(_mk_entry("Parallel"), g, children)
    assert set(out) == {"Parallel.a", "Parallel.b", "Parallel.c"}
    for child_grad in out.values():
        assert child_grad.message == "fix"
        assert child_grad.severity == 0.4


async def test_router_split_taken_branch_gets_grad_and_untaken_gets_null() -> None:
    # Build OperadOutput-shaped wrappers so _response_of unwraps them.
    class _Env:
        def __init__(self, r: BaseModel) -> None:
            self.response = r

    switch_response = B(value=42)
    branch_a_response = B(value=42)  # matches
    branch_b_response = B(value=99)  # does not match

    switch_entry = _mk_entry("Router", output=_Env(switch_response))
    router_entry = _mk_entry("Router.router", output=_Env(B(value=0)))
    branch_a_entry = _mk_entry("Router.branch_a", output=_Env(branch_a_response))
    branch_b_entry = _mk_entry("Router.branch_b", output=_Env(branch_b_response))

    g = TextualGradient(message="fix", severity=0.8)
    out = _router_split(
        switch_entry, g, [router_entry, branch_a_entry, branch_b_entry]
    )
    assert out["Router.branch_a"].message == "fix"
    assert out["Router.branch_a"].severity == 0.8
    assert out["Router.branch_b"].severity == 0.0
    assert out["Router.router"].severity == 0.0


async def test_router_split_no_match_gives_everyone_null() -> None:
    class _Env:
        def __init__(self, r: BaseModel) -> None:
            self.response = r

    switch_entry = _mk_entry("Router", output=_Env(B(value=1)))
    branch_a_entry = _mk_entry("Router.branch_a", output=_Env(B(value=2)))

    g = TextualGradient(message="fix", severity=0.8)
    out = _router_split(switch_entry, g, [branch_a_entry])
    assert out["Router.branch_a"].severity == 0.0


async def test_generic_composite_rule_warns_once_per_class() -> None:
    from operad.optim.backward import _GENERIC_WARNED

    _GENERIC_WARNED.discard("FakeLeaf")  # reset for idempotent test run

    g = TextualGradient(message="fix", severity=0.3)
    children = [_mk_entry("X.a"), _mk_entry("X.b")]
    entry = _mk_entry("X")

    with pytest.warns(RuntimeWarning, match="no structural split rule"):
        out = _generic_composite_rule(entry, g, children)
    assert out["X.a"].message == "fix"
    assert out["X.b"].message == "fix"
