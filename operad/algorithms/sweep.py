"""Sweep: Cartesian parameter grid over a seed Agent.

``Sweep`` builds one cloned, re-parameterised Agent per combination of
the provided parameter value lists, builds them all, runs them against
a single input under a concurrency bound, and returns a typed report.

Like other algorithms, ``Sweep`` is a plain class with ``run(x)``, not
an ``Agent`` subclass. The ``seed`` agent is a **class-level default**
so callers only supply the grid and algorithm knobs; subclass to swap
in a different seed.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from typing import Any, ClassVar, Generic

from pydantic import BaseModel, ConfigDict, Field

from ..agents.reasoning.components import Reasoner
from ..agents.reasoning.schemas import Answer, Candidate, Score, Task
from ..core.agent import Agent, In, Out
from ..runtime.observers.base import (
    _enter_algorithm_run,
    _enter_synthetic_child_run,
    emit_algorithm_event,
)
from ..utils.paths import set_path


class SweepCell(BaseModel, Generic[In, Out]):
    """One realised combination: the parameter assignment and its output."""

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Dotted-path → value map applied to the seed clone.",
    )
    output: Out = Field(
        description="Typed output of the built agent on the sweep input.",
    )
    score: float | None = Field(
        default=None,
        description="Optional higher-is-better score assigned to this cell.",
    )
    judge_rationale: str | None = Field(
        default=None,
        description="Optional natural-language rationale from the judge.",
    )
    child_run_id: str | None = Field(
        default=None,
        description="Dashboard run id for the cell agent invocation.",
    )
    judge_run_id: str | None = Field(
        default=None,
        description="Dashboard run id for the judge invocation, if any.",
    )
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SweepReport(BaseModel, Generic[In, Out]):
    """Flat list of cells — one per Cartesian combination."""

    cells: list[SweepCell[In, Out]] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Sweep(Generic[In, Out]):
    """Run a parameter grid in parallel over clones of the class-level seed.

    ``parameters`` maps dotted attribute paths (e.g.
    ``"config.sampling.temperature"``) to lists of values. Every
    combination of values spawns one ``seed.clone()``; each clone is
    re-parameterised via :func:`operad.utils.paths.set_path`, rebuilt,
    and invoked with ``x``.

    Concurrency is bounded by ``concurrency`` on top of whatever bound
    the slot registry applies per-backend. Combinations are capped at
    ``max_combinations`` to prevent accidental blow-ups — a single
    3-axis grid can reach into the thousands quickly.
    """

    seed: ClassVar[Agent] = Reasoner(input=Task, output=Answer)
    judge: ClassVar[Agent[Any, Any] | None] = None

    def __init__(
        self,
        parameters: dict[str, list[Any]],
        *,
        context: str = "",
        concurrency: int = 4,
        max_combinations: int = 1024,
    ) -> None:
        if concurrency < 1:
            raise ValueError(f"concurrency must be >= 1, got {concurrency}")
        if max_combinations < 1:
            raise ValueError(
                f"max_combinations must be >= 1, got {max_combinations}"
            )
        total = 1
        for v in parameters.values():
            total *= len(v)
        if total > max_combinations:
            raise ValueError(
                f"sweep would produce {total} combinations, exceeding "
                f"max_combinations={max_combinations}; tighten the grid "
                f"or raise the cap"
            )

        cls = type(self)
        self.seed = cls.seed.clone(context=context)
        self.judge = cls.judge.clone(context=context) if cls.judge is not None else None

        self.context = context
        self.parameters = parameters
        self.concurrency = concurrency
        self.max_combinations = max_combinations

    async def run(self, x: In) -> SweepReport[In, Out]:
        algo_path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=algo_path,
                payload={"concurrency": self.concurrency, "axes": list(self.parameters)},
                started_at=started,
            )
            try:
                combos = list(_cartesian(self.parameters))
                if not combos:
                    await emit_algorithm_event(
                        "algo_end",
                        algorithm_path=algo_path,
                        payload={"cells": 0},
                        started_at=started,
                        finished_at=time.time(),
                    )
                    return SweepReport[In, Out](cells=[])

                agents: list[Agent[In, Out]] = []
                for combo in combos:
                    agent = self.seed.clone()
                    for dotted, value in combo.items():
                        set_path(agent, dotted, value)
                    agents.append(agent)

                build_targets: list[Agent[Any, Any]] = [*agents]
                if self.judge is not None:
                    build_targets.append(self.judge)
                await asyncio.gather(
                    *(a.abuild() for a in build_targets if not a._built)
                )

                sem = asyncio.Semaphore(self.concurrency)
                outputs = await asyncio.gather(
                    *(_bounded(sem, _invoke_child(a, x)) for a in agents)
                )
                judge_outputs = (
                    await asyncio.gather(
                        *(
                            _bounded(
                                sem,
                                _invoke_child(
                                    self.judge,
                                    Candidate(input=x, output=out.response),
                                ),
                            )
                            for out in outputs
                        )
                    )
                    if self.judge is not None
                    else [None] * len(outputs)
                )

                cells = [
                    _cell_from_output(combo, out, judge_out)
                    for combo, out, judge_out in zip(combos, outputs, judge_outputs)
                ]
                for i, cell in enumerate(cells):
                    await emit_algorithm_event(
                        "cell",
                        algorithm_path=algo_path,
                        payload=_cell_payload(i, cell),
                    )
                scored = [
                    (i, cell.score)
                    for i, cell in enumerate(cells)
                    if cell.score is not None
                ]
                best_cell_index = None
                best_score = None
                if scored:
                    best_cell_index, best_score = max(scored, key=lambda item: item[1])
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=algo_path,
                    payload={
                        "cells": len(cells),
                        "best_cell_index": best_cell_index,
                        "score": best_score,
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return SweepReport[In, Out](cells=cells)
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=algo_path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise


def _cartesian(parameters: dict[str, list[Any]]) -> list[dict[str, Any]]:
    if not parameters:
        return [{}]
    keys = list(parameters)
    value_lists = [parameters[k] for k in keys]
    return [dict(zip(keys, values)) for values in itertools.product(*value_lists)]


async def _bounded(sem: asyncio.Semaphore, coro: Any) -> Any:
    async with sem:
        return await coro


async def _invoke_child(agent: Agent[Any, Any], x: Any) -> Any:
    with _enter_synthetic_child_run():
        return await agent(x)


def _cell_from_output(
    parameters: dict[str, Any],
    out: Any,
    judge_out: Any | None,
) -> SweepCell[Any, Any]:
    score: float | None = None
    rationale: str | None = None
    judge_run_id: str | None = None
    if judge_out is not None:
        score_obj = judge_out.response
        raw_score = getattr(score_obj, "score", None)
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)
        raw_rationale = getattr(score_obj, "rationale", None)
        if isinstance(raw_rationale, str):
            rationale = raw_rationale
        judge_run_id = getattr(judge_out, "run_id", None) or None
    return SweepCell[Any, Any](
        parameters=parameters,
        output=out.response,
        score=score,
        judge_rationale=rationale,
        child_run_id=getattr(out, "run_id", None) or None,
        judge_run_id=judge_run_id,
        latency_ms=getattr(out, "latency_ms", None),
        prompt_tokens=getattr(out, "prompt_tokens", None),
        completion_tokens=getattr(out, "completion_tokens", None),
        cost_usd=getattr(out, "cost_usd", None),
    )


def _cell_payload(index: int, cell: SweepCell[Any, Any]) -> dict[str, Any]:
    payload = cell.model_dump(
        mode="json",
        exclude={"output"},
    )
    payload["cell_index"] = index
    return payload


__all__ = ["Sweep", "SweepCell", "SweepReport"]
