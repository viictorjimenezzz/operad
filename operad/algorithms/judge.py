"""Shared type primitives for algorithms and critic-style agents.

`Score` is the canonical output of an LLM judge. `Candidate[In, Out]` is
the typed wrapper that threads the original request and a generator's
output into a judge.
"""

from __future__ import annotations

from typing import Generic

from pydantic import BaseModel, ConfigDict, Field

from ..core.agent import In, Out


class Score(BaseModel):
    """Judge output: a real-valued score with an optional rationale."""

    score: float = Field(
        default=0.0,
        description="Higher-is-better score assigned to the candidate.",
    )
    rationale: str = Field(
        default="",
        description="Short natural-language justification for the score.",
    )


class Candidate(BaseModel, Generic[In, Out]):
    """Typed view a judge receives: original request + candidate answer.

    The fields are typed `Optional[...]` so that `model_construct()` (used
    by the symbolic tracer to mint sentinel inputs during `build()`)
    produces a usable Candidate. At runtime, algorithms populate both
    slots before invoking a judge; consumers may rely on that invariant.
    """

    input: In | None = Field(
        default=None,
        description="The request that produced the candidate.",
    )
    output: Out | None = Field(
        default=None,
        description="A candidate answer to be judged.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
