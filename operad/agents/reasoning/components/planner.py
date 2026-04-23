"""Goal-to-plan decomposer leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Planner(Agent[In, Out]):
    """Decompose a goal into an ordered list of concrete steps.

    The output schema typically contains a ``steps: list[str]`` (or
    ``list[Step]``) field. Subclass to specialize: a software-engineering
    planner might override ``role`` to mention tools, a travel planner
    might override ``rules`` to add budget constraints.
    """

    role = "You are a methodical planner that turns goals into small, concrete steps."
    task = (
        "Decompose the provided goal into an ordered list of concrete, "
        "actionable steps. Each step should be small enough to execute "
        "without further planning."
    )
    rules = (
        "Order steps so each one's prerequisites are satisfied by earlier steps.",
        "Prefer many small steps over a few large ones.",
        "Do not invent steps that aren't needed by the goal.",
    )
