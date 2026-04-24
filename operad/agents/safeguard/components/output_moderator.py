"""Default-forward leaf that classifies an arbitrary payload against a policy."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from ....core.agent import Agent
from ....core.config import Configuration
from ..schemas import ModerationVerdict

T = TypeVar("T", bound=BaseModel)


class OutputModerator(Agent[T, ModerationVerdict], Generic[T]):
    """Classify an arbitrary payload against an output policy.

    Default-forward leaf: the model judges the payload and emits a
    :class:`ModerationVerdict`. Subclass to tighten ``role``/``task``
    for a narrower policy surface, or to narrow ``output`` to a
    ``Literal``-constrained verdict subtype.

    Routing on the verdict (``allow`` vs. ``block``) is a caller
    concern — the composite that wraps this leaf should dispatch via a
    ``Switch`` on ``verdict.label``, not branch on payload values.
    """

    input = BaseModel
    output = ModerationVerdict

    role = "You enforce an output policy for downstream consumers."
    task = (
        "Review the payload below and decide whether it is appropriate "
        "for release. Emit 'allow' when safe; 'block' when it would "
        "produce disallowed, unsafe, or policy-violating content."
    )
    rules = (
        "Default to 'allow' for ordinary outputs; reserve 'block' for "
        "clear violations (PII exposure, hostile content, hallucinated "
        "sensitive advice).",
        "Always include a short reason (at most two sentences).",
        "List triggered categories when relevant (e.g. 'pii', 'toxicity').",
    )

    def __init__(
        self,
        *,
        schema: type[T],
        config: Configuration | None = None,
    ) -> None:
        super().__init__(config=config, input=schema, output=ModerationVerdict)
