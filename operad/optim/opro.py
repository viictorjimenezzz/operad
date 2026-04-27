"""`OPROOptimizer` — Large Language Models as Optimizers (Yang et al. 2023).

For each trainable parameter, maintain a history of `(value, score)`
pairs and ask an `OPROAgent` for a new candidate conditioned on the
history. The candidate is evaluated via a user-supplied async callback;
the optimizer accepts it when its score beats every score seen so far
for this parameter, otherwise retries (bounded by `max_retries`).
`.grad` is ignored — OPRO works from metric feedback, not textual
gradients.
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Awaitable
from inspect import cleandoc
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

from operad.core.agent import Agent
from operad.core.config import Configuration
from operad.core.agent import Example
from operad.metrics.base import Metric
from operad.optim.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter
from operad.optim.rewrite import _describe_constraint, _parse, _serialize


class OPROHistoryEntry(BaseModel):
    """One past (value, score) pair fed into the OPRO prompt."""

    value: str = Field(
        description="The serialized candidate value that was evaluated.",
    )
    score: float = Field(
        description="The objective-metric score achieved by that candidate.",
    )


class OPROInput(BaseModel):
    """Input to `OPROAgent`: current value + history window + constraint."""

    parameter_kind: str = Field(
        description="ParameterKind literal (role, task, rules, temperature, ...).",
    )
    current_value: str = Field(
        description="The parameter's current value, serialized as text.",
    )
    history: list[OPROHistoryEntry] = Field(
        default_factory=list,
        description=(
            "Recent (value, score) pairs in chronological order. Earlier "
            "entries are the ones OPRO has already tried; the model should "
            "propose a value whose score is expected to beat the best score "
            "in this list."
        ),
    )
    constraint_hint: str = Field(
        description="Plain-English constraint the new value must satisfy.",
    )


class OPROOutput(BaseModel):
    """Output of `OPROAgent`: the next candidate value."""

    new_value: str = Field(
        description=(
            "Candidate parameter value in the same serialization as "
            "`current_value`. Plain string for text kinds, JSON list for "
            "list kinds, stringified number for numeric kinds, vocab token "
            "for categorical kinds."
        ),
    )
    rationale: str = Field(
        default="",
        description="Optional justification for why this candidate should score higher.",
    )


class OPROAgent(Agent[OPROInput, OPROOutput]):
    """Propose the next value for a parameter given its score history."""

    input = OPROInput
    output = OPROOutput

    role = "You are an LLM acting as an optimizer over parameter values."
    task = cleandoc("""
        Propose a `new_value` whose objective-metric score is expected
        to beat every score in `history`. Respect `constraint_hint`
        exactly.
    """)
    rules = (
        "The `new_value` must satisfy `constraint_hint`; a violation is a hard failure.",
        "Do not repeat a value that already appears in `history` unless you have a concrete "
        "reason to believe its score would now differ.",
        "Favour concrete, specific values over vague or generic ones.",
    )
    examples = (
        Example[OPROInput, OPROOutput](
            input=OPROInput(
                parameter_kind="role",
                current_value="You help users.",
                history=[
                    OPROHistoryEntry(value="You help users.", score=0.3),
                    OPROHistoryEntry(
                        value="You are a helpful assistant.", score=0.4
                    ),
                ],
                constraint_hint="String value. Maximum length 200 characters.",
            ),
            output=OPROOutput(
                new_value=(
                    "You are a precise domain expert who answers with "
                    "references."
                ),
                rationale=(
                    "Specialising the role worked better than generic "
                    "framings; propose a more specific variant."
                ),
            ),
        ),
    )
    default_sampling = {"temperature": 0.7}


Evaluator = Callable[[Parameter[Any], Any], Awaitable[float]]
OPROFactory = Callable[[], OPROAgent | Awaitable[OPROAgent]]


class OPROOptimizer(Optimizer):
    """LLM-as-optimizer over a parameter's value history."""

    def __init__(
        self,
        params: Iterable[Parameter[Any]] | Iterable[dict[str, Any]],
        lr: float = 1.0,
        *,
        objective_metric: Metric,
        evaluator: Evaluator,
        config: Configuration | None = None,
        opro_factory: OPROFactory | None = None,
        history_k: int = 20,
        max_retries: int = 3,
    ) -> None:
        if max_retries < 1:
            raise ValueError(f"max_retries must be >= 1, got {max_retries}")
        super().__init__(params, defaults={"lr": lr, "momentum": 0.0})
        self._objective_metric = objective_metric
        self._evaluator = evaluator
        self._config = config
        self._opro_factory = opro_factory
        self._history_k = int(history_k)
        self._max_retries = int(max_retries)
        self._opro: OPROAgent | None = None

    async def _resolve_opro(self) -> OPROAgent:
        if self._opro is not None:
            return self._opro
        if self._opro_factory is None:
            built = await OPROAgent(config=self._config).abuild()
        else:
            produced = self._opro_factory()
            if inspect.isawaitable(produced):
                built = await produced
            else:
                built = produced
        self._opro = built
        return built

    async def step(self) -> None:
        items: list[tuple[Parameter[Any], ParamGroup]] = []
        for group in self.param_groups:
            for p in group.params:
                if not p.requires_grad:
                    continue
                items.append((p, group))
        if not items:
            return
        await self._apply_updates(items)

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        history: list[tuple[str, float]] = param.momentum_state.setdefault(
            "opro", []
        )
        best_score = max((s for _, s in history), default=-math.inf)
        opro_agent = await self._resolve_opro()
        hint = _describe_constraint(param.constraint)

        for _ in range(self._max_retries):
            payload = OPROInput(
                parameter_kind=param.kind,
                current_value=_serialize(param),
                history=[
                    OPROHistoryEntry(value=v, score=s)
                    for v, s in history[-self._history_k :]
                ],
                constraint_hint=hint,
            )
            envelope = await opro_agent(payload)
            resp: OPROOutput = envelope.response
            raw_new = resp.new_value

            try:
                parsed = _parse(raw_new, param)
                if param.constraint is not None:
                    coerced = param.constraint.validate(parsed)
                    if coerced != parsed:
                        raise ValueError("candidate coerced by constraint")
                    parsed = coerced
            except Exception:
                continue

            score = float(await self._evaluator(param, parsed))
            history.append((raw_new, score))
            self._truncate_history(history)
            if score > best_score:
                param.write(parsed)
                return
            best_score = max(best_score, score)

    def _truncate_history(self, history: list[tuple[str, float]]) -> None:
        overflow = len(history) - self._history_k
        if overflow > 0:
            del history[:overflow]


__all__ = [
    "Evaluator",
    "OPROAgent",
    "OPROHistoryEntry",
    "OPROInput",
    "OPROOptimizer",
    "OPROOutput",
]
