"""Goal-to-plan decomposer leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Planner(Agent[In, Out]):
    """Decompose a goal into an ordered list of concrete steps.

    The output schema typically contains a ``steps: list[str]`` (or
    ``list[Step]``) field. Subclass to specialize: a software-engineering
    planner might override ``role`` to mention tools, a travel planner
    might override ``rules`` to add budget constraints.

    A canonical few-shot::

        from pydantic import BaseModel, Field
        from operad import Example

        class Goal(BaseModel):
            goal: str = Field(description="What to accomplish.")

        class Plan(BaseModel):
            steps: list[str] = Field(default_factory=list)

        examples = (
            Example[Goal, Plan](
                input=Goal(goal="Bake a loaf of bread."),
                output=Plan(steps=[
                    "Mix flour, water, salt, yeast.",
                    "Knead the dough for ten minutes.",
                    "Let rise for one hour.",
                    "Shape and bake at 220C for 30 minutes.",
                ]),
            ),
        )
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
