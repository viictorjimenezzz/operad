# triage_reply — composition + evolution, in one demo

A small customer-support tree (`Switch` + `Router`-style leaf +
`Sequential` + four responders) is evolved over six generations via
`Agent.auto_tune`. Every leaf is a deterministic offline component, so
the whole demo runs without a model server.

```
Switch                          (Ticket -> Reply)
├── router  : RouterLeaf        (Ticket -> RouteChoice)
└── branches
    ├── billing : BillingResponder
    ├── tech    : Sequential
    │             ├── TechAnalyzer  (Ticket -> Diagnosis)
    │             └── TechResponder (Diagnosis -> Reply)
    └── general : GeneralResponder
```

The seed is intentionally weak — the router has zero rules (so it
always falls back to `"general"`) and every responder has a cold role
and no rules (so replies are short and unwarm). The mutation pool in
`mutations.py` targets specific sub-paths, so survivors accumulate
improvements across multiple branches generation over generation.

## Quickstart

```bash
# offline, terminal only
uv run python apps/demos/triage_reply/run.py

# offline, with the live web dashboard (two terminals)
operad-dashboard --port 7860                                  # terminal A
uv run python apps/demos/triage_reply/run.py --dashboard      # terminal B
```

Expect the fitness curve to climb from ~0.3 to ~0.9 over six
generations. The dashboard's **Graph** panel renders the five-node
topology; the **Evolution** and **Mutation heatmap** panels show which
ops on which paths drove the climb.
