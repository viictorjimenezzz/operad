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

import contextlib
import inspect
import math
import time
import uuid
from collections.abc import Awaitable
from inspect import cleandoc
from typing import Any, AsyncIterator, Callable, Iterable

from pydantic import BaseModel, Field

from operad.core.agent import Agent
from operad.core.config import Configuration
from operad.core.agent import Example
from operad.metrics.metric import Metric
from operad.optim.parameter import Parameter
from operad.optim.backprop.rewrite import _describe_constraint, _parse, _serialize
from operad.optim.optimizers.optimizer import Optimizer, ParamGroup
from operad.runtime.observers import base as _obs
from operad.runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Optimizer agent.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Optimizer.
# ---------------------------------------------------------------------------


class OPROOptimizer(Optimizer):
    """LLM-as-optimizer over a parameter's value history."""

    auto_session_in_trainer = True

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
        self._algo_run_id: str | None = None
        self._step_index = 0
        self._best_score: float | None = None

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
        if self._algo_run_id is None:
            async with self.session():
                await self._step_with_context(items)
            return
        await self._step_with_context(items)

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator["OPROOptimizer"]:
        owns_session = self._algo_run_id is None
        if owns_session:
            self._algo_run_id = uuid.uuid4().hex
        run_id = self._algo_run_id or uuid.uuid4().hex
        parent_run_id = _obs._RUN_ID.get()
        metadata = (
            {"parent_run_id": parent_run_id}
            if parent_run_id is not None and parent_run_id != run_id
            else {}
        )
        if owns_session:
            with _enter_algorithm_run(run_id, reuse_existing=False):
                await emit_algorithm_event(
                    "algo_start",
                    algorithm_path=type(self).__name__,
                    payload={
                        "params": [p.path for p in self._all_params()],
                        "history_window": self._history_k,
                        "max_retries": self._max_retries,
                    },
                    started_at=time.time(),
                    metadata=metadata,
                )
        try:
            yield self
            if owns_session:
                with _enter_algorithm_run(run_id, reuse_existing=False):
                    await emit_algorithm_event(
                        "algo_end",
                        algorithm_path=type(self).__name__,
                        payload={
                            "steps": self._step_index,
                            "best_score": self._best_score,
                            "final_values": {
                                p.path: str(p.read()) for p in self._all_params()
                            },
                        },
                        started_at=time.time(),
                        finished_at=time.time(),
                    )
        except Exception as e:
            if owns_session:
                with _enter_algorithm_run(run_id, reuse_existing=False):
                    await emit_algorithm_event(
                        "algo_error",
                        algorithm_path=type(self).__name__,
                        payload={"type": type(e).__name__, "message": str(e)},
                        started_at=time.time(),
                        finished_at=time.time(),
                    )
            raise
        finally:
            if owns_session:
                self._algo_run_id = None

    async def _step_with_context(
        self,
        items: list[tuple[Parameter[Any], ParamGroup]],
    ) -> None:
        if self._algo_run_id is None:
            await self._apply_updates(items)
            return
        with _enter_algorithm_run(self._algo_run_id, reuse_existing=False):
            await self._apply_updates(items)

    def _all_params(self) -> list[Parameter[Any]]:
        return [p for group in self.param_groups for p in group.params]

    async def _apply_param_update(
        self, param: Parameter[Any], group: ParamGroup
    ) -> None:
        history: list[tuple[str, float]] = param.momentum_state.setdefault(
            "opro", []
        )
        best_score = max((s for _, s in history), default=-math.inf)
        if history:
            history_best = max(s for _, s in history)
            if self._best_score is None or history_best > self._best_score:
                self._best_score = history_best
        opro_agent = await self._resolve_opro()
        hint = _describe_constraint(param.constraint)

        for _ in range(self._max_retries):
            self._step_index += 1
            step_index = self._step_index
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
            await emit_algorithm_event(
                "iteration",
                algorithm_path=type(self).__name__,
                payload={
                    "iter_index": step_index,
                    "step_index": step_index,
                    "phase": "propose",
                    "param_path": param.path,
                    "candidate_value": raw_new,
                    "history_size": len(history),
                },
            )

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
            accepted = score > best_score
            await emit_algorithm_event(
                "iteration",
                algorithm_path=type(self).__name__,
                payload={
                    "iter_index": step_index,
                    "step_index": step_index,
                    "phase": "evaluate",
                    "param_path": param.path,
                    "candidate_value": raw_new,
                    "score": score,
                    "accepted": accepted,
                },
            )
            if self._best_score is None or score > self._best_score:
                self._best_score = score
            if accepted:
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
