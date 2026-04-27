"""Offline tests for `operad.optim.optimizers.momentum.MomentumTextGrad`."""

from __future__ import annotations

from typing import Any

import pytest

from operad.optim.backprop.rewrite import (
    RewriteRequest,
    RewriteResponse,
    TextRewriter,
)
from operad.optim.optimizers.momentum import (
    GradSummarizer,
    MomentumInput,
    MomentumTextGrad,
)
from operad.optim.parameter import TextParameter, TextualGradient
from tests._helpers.fake_leaf import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


class StubSummarizer(GradSummarizer):
    """Records the histories it was shown and returns a canned summary."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[MomentumInput] = []

    async def forward(self, x: MomentumInput) -> TextualGradient:  # type: ignore[override]
        if hasattr(x, "history"):
            self.calls.append(x)
        return TextualGradient(message="summarised", severity=0.8)


class RecordingTextRewriter(TextRewriter):
    """Records the gradient message the rewriter was invoked with."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gradient_messages: list[str] = []

    async def forward(self, x: RewriteRequest) -> RewriteResponse:  # type: ignore[override]
        old = getattr(x, "old_value", "")
        grad = getattr(x, "gradient", "")
        if old and grad:
            self.gradient_messages.append(grad)
        return RewriteResponse(new_value=f"{old} [revised]")


def _make_role_param(
    cfg: Any, initial: str = "initial"
) -> tuple[FakeLeaf, TextParameter]:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = initial
    return leaf, TextParameter.from_agent(leaf, "role", "role")


async def _built_summarizer(cfg: Any) -> StubSummarizer:
    return await StubSummarizer(config=cfg).abuild()


async def _built_rewriter(cfg: Any) -> RecordingTextRewriter:
    return await RecordingTextRewriter(config=cfg).abuild()


async def test_history_grows_and_rewriter_sees_summary(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "role-0")
    summarizer = await _built_summarizer(cfg)
    rewriter = await _built_rewriter(cfg)

    opt = MomentumTextGrad(
        [p],
        lr=1.0,
        rewriter_factory=lambda kind: rewriter,
        summarizer_factory=lambda: summarizer,
        momentum=1.0,  # no decay, easier to reason about
    )

    p.grad = TextualGradient(message="grad-a", severity=0.5)
    await opt.step()

    p.grad = TextualGradient(message="grad-b", severity=0.6)
    await opt.step()

    history = p.momentum_state["momentum"]["history"]
    assert [h.message for h in history] == ["grad-a", "grad-b"]
    assert len(summarizer.calls) == 2
    # Second call should carry both entries of history.
    assert [g.message for g in summarizer.calls[1].history] == ["grad-a", "grad-b"]
    # The rewriter only ever sees the summarised message, never the raw grads.
    assert rewriter.gradient_messages == ["summarised", "summarised"]


async def test_history_truncates_to_k(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "role-0")
    summarizer = await _built_summarizer(cfg)
    rewriter = await _built_rewriter(cfg)

    opt = MomentumTextGrad(
        [p],
        lr=1.0,
        rewriter_factory=lambda kind: rewriter,
        summarizer_factory=lambda: summarizer,
        history_k=3,
        momentum=1.0,
    )

    for i in range(5):
        p.grad = TextualGradient(message=f"g-{i}", severity=0.5)
        await opt.step()

    history = p.momentum_state["momentum"]["history"]
    assert [h.message for h in history] == ["g-2", "g-3", "g-4"]


async def test_decay_shrinks_past_severity(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "role-0")
    summarizer = await _built_summarizer(cfg)
    rewriter = await _built_rewriter(cfg)

    opt = MomentumTextGrad(
        [p],
        lr=1.0,
        rewriter_factory=lambda kind: rewriter,
        summarizer_factory=lambda: summarizer,
        momentum=0.5,
    )

    p.grad = TextualGradient(message="first", severity=1.0)
    await opt.step()
    p.grad = TextualGradient(message="second", severity=1.0)
    await opt.step()

    history = p.momentum_state["momentum"]["history"]
    assert [h.message for h in history] == ["first", "second"]
    # `first` was decayed once during step 2 (from 1.0 → 0.5).
    assert history[0].severity == pytest.approx(0.5)
    assert history[1].severity == pytest.approx(1.0)


async def test_summarizer_zero_severity_skips_rewriter(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "unchanged")

    class NullSummarizer(GradSummarizer):
        async def forward(self, x: MomentumInput) -> TextualGradient:  # type: ignore[override]
            return TextualGradient.null_gradient()

    summarizer = await NullSummarizer(config=cfg).abuild()
    rewriter = await _built_rewriter(cfg)

    opt = MomentumTextGrad(
        [p],
        lr=1.0,
        rewriter_factory=lambda kind: rewriter,
        summarizer_factory=lambda: summarizer,
        momentum=1.0,
    )

    p.grad = TextualGradient(message="tighten", severity=1.0)
    await opt.step()

    assert p.value == "unchanged"
    assert rewriter.gradient_messages == []


async def test_summarizer_built_once_across_steps(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "role-0")
    built: list[GradSummarizer] = []

    async def factory() -> GradSummarizer:
        inst = await StubSummarizer(config=cfg).abuild()
        built.append(inst)
        return inst

    rewriter = await _built_rewriter(cfg)
    opt = MomentumTextGrad(
        [p],
        lr=1.0,
        rewriter_factory=lambda kind: rewriter,
        summarizer_factory=factory,
        momentum=1.0,
    )

    for _ in range(3):
        p.grad = TextualGradient(message="g", severity=0.5)
        await opt.step()

    assert len(built) == 1
