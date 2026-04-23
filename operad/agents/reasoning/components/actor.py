"""Thought-to-action decision leaf.

Used by ``ReAct`` (and future tool-using patterns) as the "Act" step:
turn a plan or thought into a concrete, executable action.
"""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Actor(Agent[In, Out]):
    """Turn a plan or thought into a concrete next action.

    Pair with an upstream ``Reasoner`` that produces the thought and a
    downstream ``Extractor`` (or real tool executor) that consumes the
    action. The output schema typically has a short action name plus
    whatever arguments the action needs.

    A canonical few-shot on a ``Thought -> Action`` specialization::

        from operad import Example
        from operad.agents.reasoning.react import Thought, Action

        examples = (
            Example[Thought, Action](
                input=Thought(
                    reasoning="Need to look up today's exchange rate.",
                    next_action="query a currency API",
                ),
                output=Action(
                    name="fetch_rate",
                    details="GET /rates?from=USD&to=EUR",
                ),
            ),
        )
    """

    role = "You are a decisive actor that turns plans into concrete actions."
    task = (
        "Given the preceding thought and the proposed next step, emit a "
        "single concrete Action with a short name and the details needed "
        "to execute it."
    )
    rules = (
        "Pick exactly one action.",
        "Prefer small, verifiable actions over large compound ones.",
        "Make every argument explicit; do not assume unstated defaults.",
    )
