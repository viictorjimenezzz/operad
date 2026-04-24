"""Synthesizer leaf: reads a finished debate record and emits one answer."""

from __future__ import annotations

from ...reasoning.components.reasoner import Reasoner
from ...reasoning.schemas import Answer
from ..schemas import DebateRecord


class Synthesizer(Reasoner):
    """Collapse a full ``DebateRecord`` into a single final ``Answer``.

    Runs once at the end of a debate. Sees every proposal and every
    critique; its job is to resolve the debate, not to re-enter it.
    Subclass to customize output schema or synthesis style.
    """

    input = DebateRecord
    output = Answer

    role = "You are an impartial synthesizer who resolves multi-party debates."
    task = (
        "Read the full debate record — the original topic, every "
        "proposal, and every critique — and produce a single final "
        "answer that reflects the best-supported position. Briefly "
        "explain the key reasoning; then commit to the answer."
    )
    rules = (
        "Do not introduce claims absent from the record.",
        "Weigh critiques seriously; do not default to the majority view.",
        "Be decisive: the output is one answer, not a summary.",
    )
    default_sampling = {"temperature": 0.3}


__all__ = ["Synthesizer"]
