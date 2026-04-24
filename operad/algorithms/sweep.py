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
from ..agents.reasoning.schemas import Answer, Task
from ..core.agent import Agent, In, Out
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
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

                await asyncio.gather(*(a.abuild() for a in agents))

                sem = asyncio.Semaphore(self.concurrency)
                outputs = await asyncio.gather(
                    *(_bounded(sem, a(x)) for a in agents)
                )

                cells = [
                    SweepCell[In, Out](parameters=combo, output=out.response)
                    for combo, out in zip(combos, outputs)
                ]
                for i, combo in enumerate(combos):
                    await emit_algorithm_event(
                        "cell",
                        algorithm_path=algo_path,
                        payload={
                            "cell_index": i,
                            "parameters": combo,
                            "score": None,
                        },
                    )
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=algo_path,
                    payload={"cells": len(cells)},
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


__all__ = ["Sweep", "SweepCell", "SweepReport"]
