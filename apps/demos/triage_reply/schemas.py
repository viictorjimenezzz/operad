"""Typed edges for the triage_reply demo.

A tiny customer-support pipeline. Every edge carries a Pydantic model
with `Field(description=...)` populated so the renderer (and any
downstream debugger) can show what each field means.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from operad.agents.reasoning.schemas import Choice


Intent = Literal["billing", "tech", "general"]


class Ticket(BaseModel):
    text: str = Field(default="", description="The customer's message.")


class Diagnosis(BaseModel):
    text: str = Field(default="", description="Tech analyst's read of the issue.")
    severity: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="How urgent the analyst judges the issue to be.",
    )


class Reply(BaseModel):
    text: str = Field(default="", description="The reply sent back to the customer.")
    intent: Intent = Field(
        default="general",
        description="The intent of the responder that produced the reply.",
    )


class RouteChoice(Choice[Intent]):
    """The router's decision: which branch handles this ticket."""


__all__ = ["Diagnosis", "Intent", "Reply", "RouteChoice", "Ticket"]
