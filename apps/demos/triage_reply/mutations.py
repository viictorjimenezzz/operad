"""Per-path mutation pool for the triage_reply demo.

`EvoGradient` samples uniformly from this list each generation. Every
op targets a specific sub-path of the composed tree, so improvements
accumulate across branches as the population evolves. Paths reflect
the topology in `tree.py`:

- ``router``                 — routing leaf
- ``branch_billing``         — billing responder
- ``branch_tech.stage_0``    — tech analyzer
- ``branch_tech.stage_1``    — tech responder
- ``branch_general``         — general responder
"""

from __future__ import annotations

from operad.utils.ops import AppendRule, Op, TweakRole


def build_mutations() -> list[Op]:
    return [
        # Router: keyword-cue rules teach the leaf to recognise intents.
        AppendRule(
            path="router",
            rule="billing keywords: invoice, charge, refund, bill, payment",
        ),
        AppendRule(
            path="router",
            rule="tech keywords: error, broken, crash, bug, freeze, slow",
        ),
        # Billing branch
        AppendRule(
            path="branch_billing",
            rule="acknowledge the customer's frustration",
        ),
        AppendRule(
            path="branch_billing",
            rule="ask for the invoice number",
        ),
        TweakRole(
            path="branch_billing",
            role="You are a warm, friendly billing specialist.",
        ),
        # Tech branch — analyzer
        AppendRule(
            path="branch_tech.stage_0",
            rule="identify the affected component",
        ),
        AppendRule(
            path="branch_tech.stage_0",
            rule="check the most recent error message",
        ),
        # Tech branch — responder
        AppendRule(
            path="branch_tech.stage_1",
            rule="suggest a concrete next step",
        ),
        TweakRole(
            path="branch_tech.stage_1",
            role="You are a helpful, patient support engineer.",
        ),
        # General branch
        AppendRule(
            path="branch_general",
            rule="ask a clarifying question",
        ),
        TweakRole(
            path="branch_general",
            role="You are a warm, friendly assistant.",
        ),
    ]


__all__ = ["build_mutations"]
