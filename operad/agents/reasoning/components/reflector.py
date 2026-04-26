"""Reflector leaf: self-review of a prior answer.

Default-forward leaf — hits the model via ``strands`` at build time like
every other leaf. Given the original request and a candidate answer,
returns a structured ``Reflection`` that either confirms the answer or
flags specific deficiencies and proposes a revision.
"""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import Reflection, ReflectionInput


class Reflector(Agent[ReflectionInput, Reflection]):
    input = ReflectionInput
    output = Reflection

    role = "You are a careful self-reviewer."
    task = (
        "Inspect the prior answer for errors, assign a quality score in [0, 1], "
        "and propose a revision when needed."
    )
    rules = (
        "Cite specific deficiencies; no vague criticism.",
        "Always set score in [0, 1], where 1 means fully acceptable and 0 means unusable.",
        "If no deficiency exists, set needs_revision=False and leave suggested_revision empty.",
        "Do not introduce new claims the original answer cannot support.",
    )
    examples = (
        Example[ReflectionInput, Reflection](
            input=ReflectionInput(
                original_request="What is 2+2?",
                candidate_answer="2+2 is 5.",
            ),
            output=Reflection(
                score=0.0,
                needs_revision=True,
                deficiencies=["Arithmetic error: 2+2 equals 4, not 5."],
                suggested_revision="2+2 is 4.",
            ),
        ),
    )
    default_sampling = {"temperature": 0.3}


__all__ = ["Reflection", "ReflectionInput", "Reflector"]
