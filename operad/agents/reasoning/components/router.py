"""Router leaf: emits a typed ``Choice`` for downstream dispatch.

``Router`` is the leaf half of the ``Router + Switch`` pattern. It is a
standard default-forward leaf that, given some input, returns a
``Choice[T]`` — a typed label plus an optional short rationale. The
paired ``Switch`` composite (``operad.agents.reasoning.switch``) then
dispatches on that typed label.

Narrow ``Choice`` per site by subclassing with a ``Literal`` label, and
pass the concrete types to the constructor::

    from typing import Literal
    from operad import Agent, Router, Choice, RouteInput

    class Mode(Choice[Literal["search", "compute"]]):
        pass

    router = Router(config=cfg, input=RouteInput, output=Mode)

This keeps the set of allowable labels *in the type*, not a free-form
string, so ``Switch`` can reason about exhaustiveness at compose time.
"""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import Choice, RouteInput


class Router(Agent[RouteInput, Choice[str]]):
    input = RouteInput
    output = Choice[str]  # type: ignore[assignment]

    role = "You route requests to the correct handler."
    task = "Pick exactly one label from the allowed set."
    rules = (
        "Return only labels from the allowed set; never invent new labels.",
        "Prefer the most specific applicable label.",
        "Keep the reasoning to one sentence.",
    )
    examples = (
        Example[RouteInput, Choice[str]](
            input=RouteInput(query="What's the weather in Paris?"),
            output=Choice[str](label="lookup", reasoning="External fact needed."),
        ),
    )
    default_sampling = {"temperature": 0.0, "max_tokens": 64}


__all__ = ["Choice", "RouteInput", "Router"]
