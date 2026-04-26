"""Proposer leaf: generates one opinionated answer to a debate topic."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Example
from ...reasoning.components.reasoner import Reasoner
from ..schemas import DebateTopic, Proposal


class Proposer(Reasoner):
    """Generate a single concrete proposal for a ``DebateTopic``.

    Used by ``Debate`` as one of N proposers. Each clone sees the same
    topic but is expected (via sampling variance or seeded configs) to
    produce a distinct angle. Subclass to specialize role or rules for
    a domain-specific debate.
    """

    input = DebateTopic
    output = Proposal

    role = cleandoc("""
        You are an opinionated proposer in a structured debate. You
        commit to a single, defensible position on the topic you are
        given and justify it in plain language.

        You are one of several proposers whose answers will be
        critiqued and then synthesised into a final decision. Your
        value to the debate comes from specificity and defensibility,
        not from balance.
    """)
    task = cleandoc("""
        Read the debate topic and produce one concrete proposal.
        Combine two layers into a position that is both clear and
        defensible:

        - **Topic layer** — the specific question or claim under
          debate, together with any ``details`` the caller supplied
          (stance, constraints, supporting material).
        - **Stance layer** — a single position you are willing to
          defend, grounded in reasoning the critic can engage with.
    """)
    rules = (
        cleandoc("""
            Stance commitment:
              - Commit to one specific position; avoid "on the one hand / on the other hand" framing.
              - Do not hedge into neutrality or list alternatives as the primary answer.
              - State the position early so the critic can engage with it directly.
        """),
        cleandoc("""
            Justification:
              - Ground every claim in reasoning the critic can evaluate. Unsupported assertions weaken the debate.
              - Prefer concrete mechanisms, concrete examples, or concrete trade-offs over abstract appeals.
              - Keep the justification proportional to the claim; do not pad.
        """),
        cleandoc("""
            Scope:
              - Keep the proposal focused — one position per turn, one line of argument.
              - Do NOT preempt the critic by listing counter-arguments; that is their role.
              - Do NOT reference other proposers; you answer the topic directly, not their takes.
        """),
        cleandoc("""
            Output shape:
              - The ``content`` field carries the full proposal in natural language.
              - The ``author`` field identifies this proposer; leave it empty if unset — the algorithm fills it.
              - Do NOT wrap the proposal in JSON, code fences, or any container.
        """),
    )
    examples = (
        Example[DebateTopic, Proposal](
            input=DebateTopic(
                topic="Should a small team adopt a monorepo for its three services?",
                details="Team is 6 engineers; services share auth code today via a copied module.",
            ),
            output=Proposal(
                content=(
                    "Yes — a monorepo is the right move. With six engineers and a "
                    "shared auth module that is already being copy-pasted, the "
                    "coordination cost of keeping three repos consistent already "
                    "exceeds the tooling cost of a monorepo. A single repo lets "
                    "them refactor auth atomically, run one CI config, and avoid "
                    "cross-repo version-skew bugs that a six-person team cannot "
                    "afford to triage."
                ),
                author="",
            ),
        ),
    )
    default_sampling = {"temperature": 0.9}


__all__ = ["Proposer"]
