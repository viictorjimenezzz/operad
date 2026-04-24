"""Offline tests for `operad.optim.sgd.TextualGradientDescent`.

Every rewriter is stubbed via the same subclass-and-override pattern
used in `tests/optim/test_rewrite.py`; no provider is ever contacted.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from operad.optim import (
    RewriteRequest,
    RewriteResponse,
    TextParameter,
    TextRewriter,
    TextualGradient,
    TextualGradientDescent,
)
from tests._helpers.fake_leaf import A, B, FakeLeaf


class StubTextRewriter(TextRewriter):
    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        old = getattr(x, "old_value", "")
        return RewriteResponse(new_value=f"{old} [revised]")


class LRRecordingRewriter(TextRewriter):
    """Stub rewriter that records the `lr` value the optimizer passed in."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.seen_lrs: list[float] = []

    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        old = getattr(x, "old_value", "")
        lr = getattr(x, "lr", None)
        if lr is not None and old:
            self.seen_lrs.append(float(lr))
        return RewriteResponse(new_value=f"{old} [revised]")


class SleepingRewriter(TextRewriter):
    def __init__(self, *args: Any, delay: float = 0.1, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._delay = delay

    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        old = getattr(x, "old_value", "")
        if not old:
            return RewriteResponse(new_value="sentinel")
        await asyncio.sleep(self._delay)
        return RewriteResponse(new_value=f"{old} [revised]")


class FailingRewriter(TextRewriter):
    async def forward(self, x: RewriteRequest) -> RewriteResponse:
        old = getattr(x, "old_value", "")
        if not old:
            return RewriteResponse(new_value="sentinel")
        raise ValueError("boom")


async def _built(cls: type[TextRewriter], cfg: Any, **kwargs: Any) -> TextRewriter:
    return await cls(config=cfg, **kwargs).abuild()


def _make_role_param(
    cfg: Any, initial: str = "initial"
) -> tuple[FakeLeaf, TextParameter]:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = initial
    return leaf, TextParameter.from_agent(leaf, "role", "role")


async def test_step_happy_path_mutates_params_and_clears_grads(cfg: Any) -> None:
    leaf0, p0 = _make_role_param(cfg, "role-0")
    leaf1, p1 = _make_role_param(cfg, "role-1")
    p0.grad = TextualGradient(message="tighten", severity=1.0)
    p1.grad = TextualGradient(message="tighten", severity=1.0)

    stub = await _built(StubTextRewriter, cfg)
    opt = TextualGradientDescent(
        [p0, p1], lr=1.0, rewriter_factory=lambda kind: stub
    )
    await opt.step()

    assert p0.value == "role-0 [revised]"
    assert p1.value == "role-1 [revised]"
    assert p0.grad is None
    assert p1.grad is None


async def test_persist_grads_keeps_grad_after_step(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg)
    grad = TextualGradient(message="tighten", severity=1.0)
    p.grad = grad

    stub = await _built(StubTextRewriter, cfg)
    opt = TextualGradientDescent(
        [p], lr=1.0, rewriter_factory=lambda kind: stub, persist_grads=True
    )
    await opt.step()

    assert p.grad is grad


async def test_requires_grad_false_skips_param(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "unchanged")
    p.requires_grad = False
    p.grad = TextualGradient(message="tighten", severity=1.0)

    stub = await _built(StubTextRewriter, cfg)
    opt = TextualGradientDescent(
        [p], lr=1.0, rewriter_factory=lambda kind: stub
    )
    await opt.step()

    assert p.value == "unchanged"
    assert p.grad is not None  # not cleared because skipped


async def test_zero_severity_grad_skips_param(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "unchanged")
    p.grad = TextualGradient.null_gradient()

    stub = await _built(StubTextRewriter, cfg)
    opt = TextualGradientDescent(
        [p], lr=1.0, rewriter_factory=lambda kind: stub
    )
    await opt.step()

    assert p.value == "unchanged"


async def test_none_grad_skips_param(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "unchanged")
    assert p.grad is None

    stub = await _built(StubTextRewriter, cfg)
    opt = TextualGradientDescent(
        [p], lr=1.0, rewriter_factory=lambda kind: stub
    )
    await opt.step()

    assert p.value == "unchanged"


async def test_per_group_lr_threaded_into_rewriter(cfg: Any) -> None:
    leaf_hi, p_hi = _make_role_param(cfg, "hi")
    leaf_lo, p_lo = _make_role_param(cfg, "lo")
    p_hi.grad = TextualGradient(message="tighten", severity=1.0)
    p_lo.grad = TextualGradient(message="tighten", severity=1.0)

    rewriter = await _built(LRRecordingRewriter, cfg)
    opt = TextualGradientDescent(
        [
            {"params": [p_hi], "lr": 0.9},
            {"params": [p_lo], "lr": 0.1},
        ],
        rewriter_factory=lambda kind: rewriter,
    )
    await opt.step()

    assert sorted(rewriter.seen_lrs) == [0.1, 0.9]


async def test_concurrency_default_runs_in_parallel(cfg: Any) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.rules = [f"r{i}" for i in range(10)]
    params = [
        TextParameter.from_agent(leaf, f"rules[{i}]", "rule_i")
        for i in range(10)
    ]
    for p in params:
        p.grad = TextualGradient(message="tighten", severity=1.0)

    rewriter = await _built(SleepingRewriter, cfg, delay=0.1)
    opt = TextualGradientDescent(
        params, lr=1.0, rewriter_factory=lambda kind: rewriter
    )

    t0 = time.perf_counter()
    await opt.step()
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"expected <1.0s with default concurrency, got {elapsed:.3f}s"
    assert all("[revised]" in v for v in leaf.rules)


async def test_concurrency_cap_serializes_work(cfg: Any) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.rules = [f"r{i}" for i in range(10)]
    params = [
        TextParameter.from_agent(leaf, f"rules[{i}]", "rule_i")
        for i in range(10)
    ]
    for p in params:
        p.grad = TextualGradient(message="tighten", severity=1.0)

    rewriter = await _built(SleepingRewriter, cfg, delay=0.1)
    opt = TextualGradientDescent(
        params, lr=1.0, rewriter_factory=lambda kind: rewriter
    )
    opt.max_concurrent_updates = 2

    t0 = time.perf_counter()
    await opt.step()
    elapsed = time.perf_counter() - t0

    assert elapsed >= 0.5, f"expected >=0.5s with cap=2, got {elapsed:.3f}s"


async def test_step_aggregates_per_parameter_errors(cfg: Any) -> None:
    leaf_a, p_ok_a = _make_role_param(cfg, "role-a")
    leaf_b, p_ok_b = _make_role_param(cfg, "role-b")
    leaf_fail = FakeLeaf(config=cfg, input=A, output=B)
    leaf_fail.task = "task-x"
    p_fail = TextParameter.from_agent(leaf_fail, "task", "task")

    for p in (p_ok_a, p_ok_b, p_fail):
        p.grad = TextualGradient(message="tighten", severity=1.0)

    ok_rewriter = await _built(StubTextRewriter, cfg)
    fail_rewriter = await _built(FailingRewriter, cfg)

    def factory(kind: str) -> TextRewriter:
        return fail_rewriter if kind == "task" else ok_rewriter

    opt = TextualGradientDescent(
        [p_ok_a, p_ok_b, p_fail], lr=1.0, rewriter_factory=factory
    )

    with pytest.raises(ExceptionGroup) as exc_info:
        await opt.step()

    assert "optimizer step failed" in str(exc_info.value)
    assert len(exc_info.value.exceptions) == 1

    assert p_ok_a.value == "role-a [revised]"
    assert p_ok_b.value == "role-b [revised]"
    assert p_fail.value == "task-x"

    assert p_fail.grad is not None
    assert p_ok_a.grad is not None
    assert p_ok_b.grad is not None


async def test_rewriter_factory_is_cached_per_kind_and_group(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg)
    p.grad = TextualGradient(message="tighten", severity=1.0)
    stub = await _built(StubTextRewriter, cfg)
    calls: list[str] = []

    def factory(kind: str) -> TextRewriter:
        calls.append(kind)
        return stub

    opt = TextualGradientDescent(
        [p], lr=1.0, rewriter_factory=factory
    )
    await opt.step()

    p.grad = TextualGradient(message="again", severity=1.0)
    await opt.step()

    assert len(calls) == 1  # cached after first step
