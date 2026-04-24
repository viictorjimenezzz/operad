"""`APEOptimizer` — Automatic Prompt Engineer (Zhou et al. 2022).

For each trainable parameter, a `CandidateGenerator` agent emits `k`
candidate values (one per `seed_index`), every candidate is scored by a
user-supplied evaluator, and the best-scoring one (if it beats the
current value's own score) replaces the parameter. APE is a pure
best-of-K over the parameter's value space — it ignores `Parameter.grad`
entirely.
"""

from __future__ import annotations

import asyncio
import inspect
import warnings
from collections.abc import Awaitable
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

from operad.core.agent import Agent
from operad.core.config import Configuration
from operad.core.example import Example
from operad.optim.optimizer import Optimizer, ParamGroup
from operad.optim.parameter import Parameter
from operad.optim.rewrite import _describe_constraint, _parse, _serialize


class APEInput(BaseModel):
    """Input to `CandidateGenerator`: one sample call for one parameter."""

    parameter_kind: str = Field(
        description="ParameterKind literal (role, task, rules, temperature, ...).",
    )
    current_value: str = Field(
        description="The parameter's current value, serialized as text.",
    )
    constraint_hint: str = Field(
        description="Plain-English constraint the candidate must satisfy.",
    )
    seed_index: int = Field(
        description=(
            "Diversification index (0..k-1). Samples with different "
            "seed_index values should explore different candidates."
        ),
    )


class APEOutput(BaseModel):
    """Output of `CandidateGenerator`: a single candidate value."""

    candidate: str = Field(
        description=(
            "Candidate value in the same serialization as `current_value`."
        ),
    )


class CandidateGenerator(Agent[APEInput, APEOutput]):
    """Propose one diversified candidate value for a parameter."""

    input = APEInput
    output = APEOutput

    role = "You are a diversifying candidate generator for a parameter value."
    task = (
        "Propose a single `candidate` value that might improve on "
        "`current_value` while respecting `constraint_hint`. Use "
        "`seed_index` as a diversification hint so distinct indices "
        "produce distinct candidates."
    )
    rules = (
        "The `candidate` must satisfy `constraint_hint`; a violation is a hard failure.",
        "Distinct `seed_index` values should yield distinct candidates; do not repeat the previous sample.",
        "Do not prefix or suffix the value with commentary — emit only the value string itself in `candidate`.",
    )
    examples = (
        Example[APEInput, APEOutput](
            input=APEInput(
                parameter_kind="role",
                current_value="You help users.",
                constraint_hint="String value. Maximum length 200 characters.",
                seed_index=0,
            ),
            output=APEOutput(
                candidate="You are a concise, domain-aware assistant."
            ),
        ),
    )
    default_sampling = {"temperature": 0.9}


Evaluator = Callable[[Parameter[Any], Any], Awaitable[float]]
GeneratorFactory = Callable[
    [], CandidateGenerator | Awaitable[CandidateGenerator]
]


class APEOptimizer(Optimizer):
    """Best-of-K candidate sampler over a parameter's value space."""

    def __init__(
        self,
        params: Iterable[Parameter[Any]] | Iterable[dict[str, Any]],
        lr: float = 1.0,
        *,
        evaluator: Evaluator,
        config: Configuration | None = None,
        generator_factory: GeneratorFactory | None = None,
        k: int = 4,
    ) -> None:
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}")
        super().__init__(params, defaults={"lr": lr, "momentum": 0.0})
        self._evaluator = evaluator
        self._config = config
        self._generator_factory = generator_factory
        self._k = int(k)
        self._generator: CandidateGenerator | None = None
        self._warned_grad_ignored = False

    async def _resolve_generator(self) -> CandidateGenerator:
        if self._generator is not None:
            return self._generator
        if self._generator_factory is None:
            built = await CandidateGenerator(config=self._config).abuild()
        else:
            produced = self._generator_factory()
            if inspect.isawaitable(produced):
                built = await produced
            else:
                built = produced
        self._generator = built
        return built

    async def step(self) -> None:
        items: list[tuple[Parameter[Any], ParamGroup]] = []
        saw_grad = False
        for group in self.param_groups:
            for p in group.params:
                if not p.requires_grad:
                    continue
                if p.grad is not None and p.grad.severity > 0:
                    saw_grad = True
                items.append((p, group))
        if saw_grad and not self._warned_grad_ignored:
            warnings.warn(
                "APEOptimizer ignores Parameter.grad; use TextualGradientDescent "
                "or MomentumTextGrad to consume textual gradients.",
                UserWarning,
                stacklevel=2,
            )
            self._warned_grad_ignored = True
        if not items:
            return
        await self._apply_updates(items)

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        generator = await self._resolve_generator()
        hint = _describe_constraint(param.constraint)
        current_value_str = _serialize(param)

        async def _sample(i: int) -> str:
            envelope = await generator(
                APEInput(
                    parameter_kind=param.kind,
                    current_value=current_value_str,
                    constraint_hint=hint,
                    seed_index=i,
                )
            )
            return envelope.response.candidate

        raw_candidates = await asyncio.gather(
            *(_sample(i) for i in range(self._k))
        )

        parsed_candidates: list[tuple[str, Any]] = []
        for raw in raw_candidates:
            try:
                parsed = _parse(raw, param)
                if param.constraint is not None:
                    coerced = param.constraint.validate(parsed)
                    if coerced != parsed:
                        continue
                    parsed = coerced
                parsed_candidates.append((raw, parsed))
            except Exception:
                continue

        if not parsed_candidates:
            return

        current_score = float(await self._evaluator(param, param.value))
        scored = await asyncio.gather(
            *(self._evaluator(param, v) for _, v in parsed_candidates)
        )
        best_idx = max(range(len(scored)), key=lambda i: float(scored[i]))
        best_score = float(scored[best_idx])
        if best_score > current_score:
            param.write(parsed_candidates[best_idx][1])


__all__ = [
    "APEInput",
    "APEOptimizer",
    "APEOutput",
    "CandidateGenerator",
    "Evaluator",
    "GeneratorFactory",
]
