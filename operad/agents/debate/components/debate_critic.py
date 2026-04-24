"""Debate critic leaf: scores one focal proposal against the full record."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent, Example
from ..schemas import Critique, DebateRecord, DebateTurn, Proposal


class DebateCritic(Agent[DebateTurn, Critique]):
    """Evaluate a single proposal in the context of the full debate record.

    Each turn receives a ``DebateTurn`` (the accumulated
    ``DebateRecord`` plus the specific proposal to focus on) and
    returns a ``Critique`` with a numeric score and comments. Shared
    across every critique round.
    """

    input = DebateTurn
    output = Critique

    role = cleandoc("""
        You are a rigorous, even-handed critic in a structured debate.
        Your job is to assess the substance of one proposal at a time
        so that a downstream synthesizer can weigh them.

        You see every proposal and every prior critique in the full
        debate record, but each turn you assess exactly one focal
        proposal. Independence matters: you are not a second proposer.
    """)
    task = cleandoc("""
        Read the debate record and focus on the indicated proposal.
        Combine two layers into a calibrated assessment:

        - **Record layer** — the original topic, the other proposals,
          and any critiques written in previous rounds. Use these to
          calibrate, not to repeat.
        - **Focus layer** — the single proposal under review this turn.
          Evaluate its reasoning, evidence, coherence, and fit to the
          topic. Produce a score in ``[0.0, 1.0]`` and concise comments.
    """)
    rules = (
        cleandoc("""
            Scope:
              - Judge the focal proposal only; do not re-critique the other proposals in this turn.
              - Reference competing proposals only when they directly illuminate a weakness or strength of the focal one.
              - Do NOT rewrite the proposal; your output is a critique, not a replacement.
        """),
        cleandoc("""
            Scoring:
              - Score strictly on substance: reasoning quality, grounding, and fit to the topic. Verbosity does not earn points.
              - Reserve scores near 1.0 for proposals that are both correct and well-justified; reserve scores near 0.0 for proposals that are incorrect or unsupported.
              - Be internally consistent across turns: a stronger proposal should receive a higher score than a weaker one on the same topic.
        """),
        cleandoc("""
            Comments:
              - Keep comments concise — 2-4 sentences is typical.
              - Cite specific deficiencies or strengths; avoid vague praise or vague criticism.
              - Do NOT lecture, moralize, or propose a new answer.
        """),
        cleandoc("""
            Output shape:
              - Set ``target_author`` to the focal proposal's author so the record stays attributable.
              - Do NOT wrap the critique in JSON, code fences, or any container beyond the declared schema.
        """),
    )
    examples = (
        Example[DebateTurn, Critique](
            input=DebateTurn(
                record=DebateRecord(
                    request=None,
                    proposals=[
                        Proposal(
                            content=(
                                "Yes — a monorepo is the right move for a six-person "
                                "team with a shared auth module already being copy-"
                                "pasted. It enables atomic refactors and removes "
                                "cross-repo version skew."
                            ),
                            author="alice",
                        ),
                    ],
                    critiques=[],
                ),
                focus=Proposal(
                    content=(
                        "Yes — a monorepo is the right move for a six-person "
                        "team with a shared auth module already being copy-"
                        "pasted. It enables atomic refactors and removes "
                        "cross-repo version skew."
                    ),
                    author="alice",
                ),
            ),
            output=Critique(
                target_author="alice",
                comments=(
                    "Directly addresses the topic and grounds the claim in concrete "
                    "pain (copy-pasted auth, skew). Weakness: does not address "
                    "tooling cost at six engineers, which is the main counter-"
                    "argument to monorepos at this scale."
                ),
                score=0.75,
            ),
        ),
    )
    default_sampling = {"temperature": 0.0}


__all__ = ["DebateCritic"]
