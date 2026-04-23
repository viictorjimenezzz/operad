"""Linear composition: `Pipeline(a, b, c)` runs `c(b(a(x)))`."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..core.agent import Agent, In, Out


class Pipeline(Agent[In, Out]):
    """Chain stages end-to-end; `build()` type-checks each handoff.

    The `input` passed at construction must match the first stage's
    `input`, each subsequent stage's `input` must match the previous
    stage's `output`, and the final stage's `output` must match the
    declared `output`. All of that is checked at ``build()`` time via
    the existing tracer.

    As a composite, ``Pipeline`` is a pure router: ``config`` is
    ``None`` because it never contacts a model on its own — stages do.
    """

    def __init__(
        self,
        *stages: Agent[Any, Any],
        input: type[In],
        output: type[Out],
    ) -> None:
        if not stages:
            raise ValueError("Pipeline requires at least one stage")
        super().__init__(config=None, input=input, output=output)
        self._stages: list[Agent[Any, Any]] = list(stages)
        for i, stage in enumerate(stages):
            setattr(self, f"stage_{i}", stage)

    async def forward(self, x: In) -> Out:  # type: ignore[override]
        current: BaseModel = x
        for stage in self._stages:
            current = await stage(current)
        return current  # type: ignore[return-value]
