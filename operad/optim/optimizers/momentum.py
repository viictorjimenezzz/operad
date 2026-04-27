"""`MomentumTextGrad` — textual-gradient descent with a rolling history.

Keeps the last `history_k` gradients per parameter and feeds them
through a small `GradSummarizer` agent to produce a single synthesised
gradient at each step. The synthesised gradient replaces the raw
`.grad` on the rewriter's input; everything else matches
`TextualGradientDescent` (kind-based rewriter resolution, per-group
`lr`, concurrency cap, optional `persist_grads`).

The per-group `momentum` float is the decay applied to each entry's
severity between steps — 1.0 means no decay, 0.9 (default) means past
entries lose 10 % of their severity per step.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from inspect import cleandoc
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

from operad.core.agent import Agent
from operad.core.config import Configuration
from operad.core.agent import Example
from operad.optim.parameter import Parameter, TextualGradient
from operad.optim.backprop.rewrite import apply_rewrite
from operad.optim.optimizers.optimizer import ParamGroup
from operad.optim.optimizers.tgd import RewriterFactory, TextualGradientDescent


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


class MomentumInput(BaseModel):
    """Input to `GradSummarizer`: a history of recent gradients."""

    parameter_kind: str = Field(
        description="The `ParameterKind` this history belongs to (role, rules, ...).",
    )
    history: list[TextualGradient] = Field(
        description=(
            "Recent gradients for one parameter, oldest first. The last "
            "entry is the current step's gradient."
        ),
    )


# ---------------------------------------------------------------------------
# Summarizer agent.
# ---------------------------------------------------------------------------


class GradSummarizer(Agent[MomentumInput, TextualGradient]):
    """Synthesise one gradient from a history of recent gradients."""

    input = MomentumInput
    output = TextualGradient

    role = "You are a disciplined synthesiser of recent parameter critiques."
    task = cleandoc("""
        Emit a single gradient that captures the consistent,
        actionable signal across the chronological list of past
        gradients for one parameter. Weight recent entries more
        heavily; discard contradictions superseded by later critiques.
    """)
    rules = (
        "Do not introduce new critiques — only synthesise what the history contains.",
        "If the history is empty or entirely zero-severity, return severity=0.0 with an empty message.",
        "Prefer specific, short messages over vague, long ones.",
    )
    examples = (
        Example[MomentumInput, TextualGradient](
            input=MomentumInput(
                parameter_kind="role",
                history=[
                    TextualGradient(message="Too generic.", severity=0.6),
                    TextualGradient(
                        message="Lacks domain authority.", severity=0.8
                    ),
                ],
            ),
            output=TextualGradient(
                message=(
                    "The role needs domain authority; make it specific to "
                    "the intended specialty."
                ),
                severity=0.7,
            ),
        ),
    )
    default_sampling = {"temperature": 0.3}


SummarizerFactory = Callable[[], GradSummarizer | Awaitable[GradSummarizer]]


# ---------------------------------------------------------------------------
# Optimizer.
# ---------------------------------------------------------------------------


class MomentumTextGrad(TextualGradientDescent):
    """Textual-gradient descent that smooths raw grads with a rolling summary.

    Extends `TextualGradientDescent` by reading `param.momentum_state
    ["momentum"]["history"]` before each rewrite: the raw gradient is
    pushed on, past entries optionally decay by the per-group `momentum`
    factor, and the list is truncated to `history_k` entries. The
    resulting history is then summarised by a single `GradSummarizer`
    (lazily built, shared across all parameters), and the summary
    gradient — not the raw one — is passed to the rewriter.
    """

    def __init__(
        self,
        params: Iterable[Parameter[Any]] | Iterable[dict[str, Any]],
        lr: float = 1.0,
        *,
        config: Configuration | None = None,
        rewriter_factory: RewriterFactory | None = None,
        summarizer_factory: SummarizerFactory | None = None,
        history_k: int = 5,
        momentum: float = 0.9,
        persist_grads: bool = False,
    ) -> None:
        super().__init__(
            params,
            lr=lr,
            config=config,
            rewriter_factory=rewriter_factory,
            persist_grads=persist_grads,
        )
        self.defaults["momentum"] = float(momentum)
        for g in self.param_groups:
            g.momentum = float(momentum)
        self._history_k = int(history_k)
        self._summarizer_factory = summarizer_factory
        self._summarizer: GradSummarizer | None = None

    async def _resolve_summarizer(self) -> GradSummarizer:
        if self._summarizer is not None:
            return self._summarizer
        if self._summarizer_factory is None:
            built = await GradSummarizer(config=self._config).abuild()
        else:
            produced = self._summarizer_factory()
            if inspect.isawaitable(produced):
                built = await produced
            else:
                built = produced
        self._summarizer = built
        return built

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        grad = param.grad
        assert grad is not None  # step() filters None/zero severity

        state = param.momentum_state.setdefault("momentum", {})
        history: list[TextualGradient] = list(state.get("history", []))
        decay = float(group.momentum)
        if decay != 1.0:
            history = [
                TextualGradient(
                    message=h.message,
                    by_field=dict(h.by_field),
                    severity=float(h.severity) * decay,
                    target_paths=list(h.target_paths),
                )
                for h in history
            ]
        history.append(grad)
        if self._history_k > 0:
            history = history[-self._history_k :]
        state["history"] = history

        summarizer = await self._resolve_summarizer()
        envelope = await summarizer(
            MomentumInput(parameter_kind=param.kind, history=list(history))
        )
        summary: TextualGradient = envelope.response
        if summary.severity <= 0:
            return

        rewriter = await self._resolve_rewriter(param.kind, group)
        await apply_rewrite(param, summary, rewriter, lr=group.lr)


__all__ = ["GradSummarizer", "MomentumInput", "MomentumTextGrad"]
