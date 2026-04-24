"""Synthesizer leaf: reads a finished debate record and emits one answer."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Example
from ...reasoning.components.reasoner import Reasoner
from ...reasoning.schemas import Answer
from ..schemas import Critique, DebateRecord, Proposal


class Synthesizer(Reasoner):
    """Collapse a full ``DebateRecord`` into a single final ``Answer``.

    Runs once at the end of a debate. Sees every proposal and every
    critique; its job is to resolve the debate, not to re-enter it.
    Subclass to customize output schema or synthesis style.
    """

    input = DebateRecord
    output = Answer

    role = cleandoc("""
        You are an impartial synthesizer who resolves multi-party
        debates. The debate is over; your output is the final answer
        that the calling application will use.

        You see the original topic, every proposal from every
        proposer, and every critique from every round. Your job is to
        weigh the record and commit to a single answer — not to
        summarise, not to moderate, not to hedge.
    """)
    task = cleandoc("""
        Read the full debate record and produce one final answer.
        Combine two layers into a decision that is both grounded and
        decisive:

        - **Record layer** — the original topic, the proposals, and
          the critiques. Weigh them on substance, not on volume or
          order.
        - **Resolution layer** — a single answer that reflects the
          best-supported position, together with a short explanation
          of the key reasoning that got you there.
    """)
    rules = (
        cleandoc("""
            Grounding:
              - Do not introduce claims absent from the record. The proposals and critiques are the complete evidence base.
              - Weigh critiques seriously; do not default to the majority view or to the first proposal.
              - When critiques exposed a decisive flaw, let it dominate; when critiques were superficial, do not let them outweigh substantive reasoning.
        """),
        cleandoc("""
            Decisiveness:
              - Commit to one answer. The output is a decision, not a summary of the debate.
              - Do NOT include phrases like "on balance, it depends" as the final answer; if the record is genuinely inconclusive, say so directly and state the best-supported position given the evidence.
        """),
        cleandoc("""
            Reasoning:
              - The ``reasoning`` field carries a short trace of the key considerations — which proposal prevailed and why, which critiques mattered.
              - Keep it proportional: 2-4 sentences is typical. Do not re-quote the entire record.
        """),
        cleandoc("""
            Output shape:
              - Populate ``reasoning`` with the decision rationale and ``answer`` with the final committed answer.
              - Do NOT wrap either field in JSON, code fences, or any container beyond the declared schema.
        """),
    )
    examples = (
        Example[DebateRecord, Answer](
            input=DebateRecord(
                request=None,
                proposals=[
                    Proposal(
                        content=(
                            "Yes — a monorepo is the right move; copy-pasted auth "
                            "and cross-repo skew already hurt this team."
                        ),
                        author="alice",
                    ),
                    Proposal(
                        content=(
                            "No — stay on three repos; monorepo tooling overhead "
                            "dominates at six engineers."
                        ),
                        author="bob",
                    ),
                ],
                critiques=[
                    Critique(
                        target_author="alice",
                        comments=(
                            "Grounded in concrete pain; does not address tooling cost."
                        ),
                        score=0.75,
                    ),
                    Critique(
                        target_author="bob",
                        comments=(
                            "Asserts tooling overhead but offers no evidence; "
                            "ignores the copy-pasted auth problem."
                        ),
                        score=0.35,
                    ),
                ],
            ),
            output=Answer(
                reasoning=(
                    "Alice's proposal is grounded in concrete, ongoing pain (copy-"
                    "pasted auth, cross-repo skew) and the critique only flagged a "
                    "gap on tooling cost. Bob's counter-proposal is assertion-"
                    "heavy and the critique dismantled its main premise. The "
                    "record supports adopting a monorepo, with tooling cost as a "
                    "secondary concern to plan for."
                ),
                answer=(
                    "Adopt a monorepo; budget a small up-front tooling investment "
                    "to mitigate overhead concerns."
                ),
            ),
        ),
    )
    default_sampling = {"temperature": 0.3}


__all__ = ["Synthesizer"]
