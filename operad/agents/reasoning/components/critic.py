"""Candidate-scoring critic leaf (LLM judge).

``Critic`` is the canonical judge for ``BestOfN``, ``VerifierLoop``, and
similar algorithms. Its input is ``Candidate[In, Out]`` — the original
request together with a candidate answer — and its output is ``Score``.
"""

from __future__ import annotations

from ....algorithms import Candidate, Score
from ....core.agent import Agent


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
