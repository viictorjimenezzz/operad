"""Instruction-preserving reformulation leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Reformulator(Agent[In, Out]):
    """Rephrase content while preserving semantics and constraints."""

    role = "You are a precise reformulator."
    task = (
        "Rephrase the input clearly and concisely while preserving the same "
        "intent, requirements, and scope."
    )
    rules = (
        "Preserve all constraints and commitments.",
        "Do not change the requested outcome.",
        "Avoid introducing new requirements.",
    )
    default_sampling = {"temperature": 0.3}
