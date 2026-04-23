"""Observation-to-answer evaluator leaf.

Used by ``ReAct`` (and future verifier/loop patterns) as the final step:
given an observation, commit to a final answer for the original task.
"""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Evaluator(Agent[In, Out]):
    """Commit to a final answer based on an observation.

    The last step of a reason-act-observe-evaluate chain. The output
    schema typically has a short ``reasoning`` field followed by the
    concrete ``answer`` so the model's commitment is explicit.

    A canonical few-shot on an ``Observation -> Answer`` specialization::

        from operad import Example
        from operad.agents.reasoning.react import Observation, Answer

        examples = (
            Example[Observation, Answer](
                input=Observation(
                    result="The lookup returned 1.09 EUR per USD.",
                    success=True,
                ),
                output=Answer(
                    reasoning="The rate lookup succeeded with a clear value.",
                    answer="1 USD = 1.09 EUR",
                ),
            ),
        )
    """

    role = "You are a careful evaluator that commits to a final answer."
    task = (
        "Given the observation, reason briefly about what it implies, "
        "then commit to the single best answer to the original task."
    )
    rules = (
        "Do not hedge beyond what the observation justifies.",
        "If the observation is insufficient, say so in the answer rather "
        "than fabricating detail.",
    )
