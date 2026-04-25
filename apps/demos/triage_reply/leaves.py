"""Offline leaves for the triage_reply demo.

Every leaf overrides `forward` so its output is a deterministic function
of declared state (`role`, `rules`, `task`) and the input. No backend is
ever contacted, so the whole demo runs without a model server.

The pattern mirrors `examples/talker_evolution.py::FakeTalker` and
`apps/demos/agent_evolution/seed.py::RuleCountLeaf`: the responder
length scales with `len(self.rules)` and warmth comes from a role
keyword. Routing knowledge lives in the `RouterLeaf`'s rules so
`AppendRule` mutations on that path can extend its keyword vocabulary.
"""

from __future__ import annotations

from operad import Agent

from schemas import Diagnosis, Intent, Reply, RouteChoice, Ticket


def _is_warm(role: str | None) -> bool:
    text = (role or "").lower()
    return any(w in text for w in ("warm", "friendly", "helpful", "patient"))


class RouterLeaf(Agent[Ticket, RouteChoice]):
    """Pick a branch label by keyword-matching the ticket against `rules`.

    Each rule of the form ``"<intent> keywords: word, word, ..."``
    contributes that word list to the router's vocabulary for that
    intent. With zero rules the router always returns ``"general"`` —
    which is the seed behaviour the evolutionary loop is meant to fix.
    """

    input = Ticket
    output = RouteChoice

    role = "You are an assistant."
    task = "Pick a branch."
    rules = ()

    async def forward(self, x: Ticket) -> RouteChoice:  # type: ignore[override]
        text = (x.text or "").lower()
        for label in ("billing", "tech"):
            for rule in self.rules:
                marker = f"{label} keywords:"
                lower = rule.lower()
                if marker not in lower:
                    continue
                suffix = lower.split(marker, 1)[1]
                tokens = [t.strip(" .,;:") for t in suffix.replace(",", " ").split()]
                if any(tok and tok in text for tok in tokens):
                    return RouteChoice.model_construct(label=label, reasoning="")
        return RouteChoice.model_construct(label="general", reasoning="")


class _Responder(Agent[Ticket, Reply]):
    """Shared base for branch responders.

    Subclasses set class-level ``INTENT`` and ``OPENER``. The reply text
    grows with rule count (each rule becomes a sentence) and gains a
    warm closer when ``role`` mentions warmth. This means
    ``AppendRule`` and ``TweakRole`` mutations targeted at the
    responder's path move fitness in a stable, monotonic direction.
    """

    input = Ticket
    output = Reply

    INTENT: Intent = "general"
    OPENER: str = "Thanks for getting in touch."

    role = "You are an assistant."
    task = "Respond."
    rules = ()

    async def forward(self, x: Ticket) -> Reply:  # type: ignore[override]
        body = self.OPENER + " "
        for rule in self.rules:
            body += f"We will {rule.lower().rstrip('.')}. "
        closer = (
            "Let us know if anything else comes up!"
            if _is_warm(self.role)
            else "Done."
        )
        return Reply.model_construct(text=f"{body}{closer}", intent=self.INTENT)


class BillingResponder(_Responder):
    INTENT: Intent = "billing"
    OPENER = "Thanks for reaching out about your billing concern."


class GeneralResponder(_Responder):
    INTENT: Intent = "general"
    OPENER = "Thanks for getting in touch."


class TechAnalyzer(Agent[Ticket, Diagnosis]):
    """Produce a Diagnosis from a Ticket.

    Diagnosis text grows with rule count (each rule contributes one
    note). Severity is fixed — only the textual content matters for the
    downstream responder.
    """

    input = Ticket
    output = Diagnosis

    role = "You are an assistant."
    task = "Analyze."
    rules = ()

    async def forward(self, x: Ticket) -> Diagnosis:  # type: ignore[override]
        notes = ["Initial assessment of the issue."]
        for rule in self.rules:
            notes.append(f"Note: {rule.rstrip('.')}.")
        return Diagnosis.model_construct(text=" ".join(notes), severity="medium")


class TechResponder(Agent[Diagnosis, Reply]):
    """Turn a Diagnosis into a Reply.

    Length comes from the analyzer's diagnosis text plus this
    responder's own rules; warmth comes from the role.
    """

    input = Diagnosis
    output = Reply

    role = "You are an assistant."
    task = "Respond."
    rules = ()

    async def forward(self, x: Diagnosis) -> Reply:  # type: ignore[override]
        body = f"Thanks for flagging this. {x.text} "
        for rule in self.rules:
            body += f"We will {rule.lower().rstrip('.')}. "
        closer = (
            "Let us know if anything else surfaces!"
            if _is_warm(self.role)
            else "Done."
        )
        return Reply.model_construct(text=f"{body}{closer}", intent="tech")


__all__ = [
    "BillingResponder",
    "GeneralResponder",
    "RouterLeaf",
    "TechAnalyzer",
    "TechResponder",
]
