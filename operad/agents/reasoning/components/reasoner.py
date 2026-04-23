"""Chain-of-thought reasoning leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Reasoner(Agent[In, Out]):
    """Produce a chain-of-thought, then a typed answer.

    Useful whenever correctness benefits from explicit deliberation.
    Subclass with concrete `input` / `output` Pydantic classes to
    specialize; the output class is expected to include both a
    ``reasoning``-like field and a final answer field so the model
    commits to its thought process before answering.

    A canonical few-shot on a ``Task -> Thought``-shaped specialization::

        from operad import Example
        from operad.agents.reasoning.schemas import Task, Thought

        examples = (
            Example[Task, Thought](
                input=Task(goal="What is 2 + 2?"),
                output=Thought(
                    reasoning="Addition: 2 + 2 sums to 4.",
                    next_action="return the answer 4",
                ),
            ),
        )

    Pass ``examples=...`` to the constructor (or set it on your
    subclass) whenever your ``input``/``output`` schemas are concrete.
    """

    role = "You are a careful, methodical reasoner."
    task = (
        "Work through the problem step-by-step, state any assumptions "
        "explicitly, then commit to a final answer."
    )
    rules = (
        "Show your reasoning before the final answer.",
        "Prefer uncertainty ('I don't know') over a confident wrong guess.",
    )
    default_sampling = {"temperature": 0.7}
