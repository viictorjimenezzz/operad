"""Compose the triage_reply demo's seed agent.

Topology::

    Router                          (input=Ticket, output=Reply)
    ├── router  : RouterLeaf        (Ticket -> RouteChoice)
    └── branches
        ├── billing : BillingResponder    (Ticket -> Reply)
        ├── tech    : Sequential             (Ticket -> Reply)
        │             ├── stage_0: TechAnalyzer  (Ticket -> Diagnosis)
        │             └── stage_1: TechResponder (Diagnosis -> Reply)
        └── general : GeneralResponder    (Ticket -> Reply)

This exercises three composition primitives — structural `Router`,
`RouteClassifier`-style
leaf, and a nested `Sequential` — in five evolvable leaves. Mutation paths
from the root therefore look like ``router``,
``branch_billing``, ``branch_tech.stage_0``,
``branch_tech.stage_1``, ``branch_general``.
"""

from __future__ import annotations

from operad.agents.pipelines import Router, Sequential

from leaves import (
    BillingResponder,
    GeneralResponder,
    RouterLeaf,
    TechAnalyzer,
    TechResponder,
)
from schemas import Reply, Ticket


def build_seed() -> Router:
    """Construct the unbuilt seed for `run.py` to evolve.

    The seed is intentionally weak: the router has no rules (so it
    always picks ``"general"``), every responder has empty rules and a
    cold role (so replies are short and unwarm). The evolutionary loop
    has plenty of room to climb from here.
    """
    tech_branch = Sequential(
        TechAnalyzer(),
        TechResponder(),
        input=Ticket,
        output=Reply,
    )
    return Router(
        router=RouterLeaf(),
        branches={
            "billing": BillingResponder(),
            "tech": tech_branch,
            "general": GeneralResponder(),
        },
        input=Ticket,
        output=Reply,
    )


__all__ = ["build_seed"]
