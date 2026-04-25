"""Hand-crafted (Ticket, expected Reply) pairs for the triage_reply demo.

Three intents × three tickets each = nine evaluation rows. Expected
``Reply.text`` is unused — the metric is reference-free on text — but
``Reply.intent`` is the ground-truth routing label that the metric
compares against the predicted intent.
"""

from __future__ import annotations

from schemas import Reply, Ticket


def build_dataset() -> list[tuple[Ticket, Reply]]:
    return [
        # Billing
        (
            Ticket(text="There's a charge on my invoice I don't recognise."),
            Reply(intent="billing"),
        ),
        (
            Ticket(text="Can I get a refund for the duplicate payment?"),
            Reply(intent="billing"),
        ),
        (
            Ticket(text="My monthly bill seems higher than usual."),
            Reply(intent="billing"),
        ),
        # Tech
        (
            Ticket(text="The app keeps showing an error when I open it."),
            Reply(intent="tech"),
        ),
        (
            Ticket(text="Something is broken — the page just freezes."),
            Reply(intent="tech"),
        ),
        (
            Ticket(text="The export crashes every time I run it."),
            Reply(intent="tech"),
        ),
        # General
        (
            Ticket(text="Hi, I just wanted to say hello."),
            Reply(intent="general"),
        ),
        (
            Ticket(text="Where can I read more about your team?"),
            Reply(intent="general"),
        ),
        (
            Ticket(text="Quick question about your hours of operation."),
            Reply(intent="general"),
        ),
    ]


__all__ = ["build_dataset"]
