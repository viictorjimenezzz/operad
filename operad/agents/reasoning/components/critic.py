"""Candidate-scoring critic leaf (LLM judge).

``Critic`` is the canonical judge for ``BestOfN``, ``VerifierLoop``, and
similar algorithms. Its input is ``Candidate[In, Out]`` — the original
request together with a candidate answer — and its output is ``Score``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ....algorithms import Candidate, Score
from ....core.agent import Agent, Example


class _CriticRequest(BaseModel):
    text: str = Field(default="", description="The original request.")


class _CriticAnswer(BaseModel):
    text: str = Field(default="", description="The candidate answer.")


class Critic(Agent[Candidate, Score]):
    """Score a candidate answer against the original request.

    Defaults to scoring in a conservative 0..1 range with a short
    rationale. Override ``task`` or ``rules`` (typically via a subclass)
    to bring in domain-specific criteria.
    """

    input = Candidate
    output = Score

    role = "You are a rigorous, calibrated critic that scores answers."
    task = (
        "Given the original request and a candidate answer, assign a score "
        "in [0.0, 1.0] and a short rationale. Higher is better."
    )
    rules = (
        "Score strictly on the candidate's alignment with the request; "
        "do not reward verbosity or style absent of substance.",
        "Reserve scores near 1.0 for unambiguously correct, complete answers.",
        "Keep the rationale under three sentences.",
    )
    examples = (
        Example[Candidate, Score](
            input=Candidate(
                input=_CriticRequest(text="What is the capital of France?"),
                output=_CriticAnswer(text="Paris."),
            ),
            output=Score(
                score=1.0,
                rationale="Directly and correctly answers the question.",
            ),
        ),
        Example[Candidate, Score](
            input=Candidate(
                input=_CriticRequest(text="What is the capital of France?"),
                output=_CriticAnswer(text="It is a European city."),
            ),
            output=Score(
                score=0.1,
                rationale="Vague; avoids naming the specific capital.",
            ),
        ),
    )
    default_sampling = {"temperature": 0.0, "max_tokens": 512}
