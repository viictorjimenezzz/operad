"""Domain-agnostic composition primitives.

`Sequential` chains stages end-to-end.
`Parallel` fans out a shared input to multiple children and combines results.
`Loop` repeats a full `Sequential` pass `n_loops` times.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel

from ..core.agent import Agent, In, Out


class Sequential(Agent[In, Out]):
    """Chain stages end-to-end; `build()` type-checks each handoff."""

    def __init__(
        self,
        *stages: Agent[Any, Any],
        input: type[In],
        output: type[Out],
        name: str | None = None,
    ) -> None:
        if not stages:
            raise ValueError("Sequential requires at least one stage")
        super().__init__(config=None, input=input, output=output, name=name)
        self._stages: list[Agent[Any, Any]] = list(stages)
        for i, stage in enumerate(stages):
            setattr(self, f"stage_{i}", stage)

    async def forward(self, x: In) -> Out:  # type: ignore[override]
        current: BaseModel = x
        for stage in self._stages:
            current = (await stage(current)).response
        return current  # type: ignore[return-value]


class Parallel(Agent[In, Out]):
    """Invoke each child with the same input via `asyncio.gather`; combine."""

    def __init__(
        self,
        children: Mapping[str, Agent[In, Any]],
        *,
        input: type[In],
        output: type[Out],
        combine: Callable[[dict[str, BaseModel]], Out],
        name: str | None = None,
    ) -> None:
        if not children:
            raise ValueError("Parallel requires at least one child")
        super().__init__(config=None, input=input, output=output, name=name)
        self._keys: list[str] = list(children)
        for key, child in children.items():
            setattr(self, key, child)
        self._combine = combine

    async def forward(self, x: In) -> Out:  # type: ignore[override]
        wrapped = await asyncio.gather(
            *(getattr(self, key)(x) for key in self._keys)
        )
        results = [w.response for w in wrapped]
        return self._combine(dict(zip(self._keys, results, strict=True)))


class Loop(Sequential[In, In]):
    """Repeat a full `Sequential` pass `n_loops` times."""

    def __init__(
        self,
        *stages: Agent[Any, Any],
        input: type[In],
        output: type[In],
        n_loops: int,
        name: str | None = None,
    ) -> None:
        if input is not output:
            raise ValueError("Loop requires `input` and `output` to be the same type")
        if n_loops < 1:
            raise ValueError("Loop requires n_loops >= 1")
        super().__init__(*stages, input=input, output=output, name=name)
        self.n_loops = n_loops

    async def forward(self, x: In) -> In:  # type: ignore[override]
        current: BaseModel = x
        for _ in range(self.n_loops):
            for stage in self._stages:
                current = (await stage(current)).response
        return current  # type: ignore[return-value]
