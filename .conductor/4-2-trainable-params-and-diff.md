# 4-2 Trainable parameters panel + AgentDiff between invocations

## Scope

Surface operad's training-time machinery in the agent view:

1. A "Trainable parameters" section in the agent edge popup that
   lists every `Parameter` with `requires_grad=True` on the
   agent, its current value, last gradient, and constraint.
2. A new drawer view, `"diff"`, that takes two invocation IDs and
   renders an `AgentDiff` between their state snapshots — i.e.
   "this agent rewrote itself between these two calls".

### You own

- `apps/frontend/src/components/agent-view/graph/`
  - Extend `agent-edge-popup.tsx` with a "Parameters" collapsible
    section.
  - `parameters-panel.tsx` (new) — renders `[(path, value,
    grad?, constraint?), ...]`.
- `apps/frontend/src/components/agent-view/drawer/views/diff/`
  - `invocation-diff.tsx` — main diff view (state → state).
  - `change-row.tsx` — one entry from `AgentDiff.changes`.
  - `index.ts` — registers `"diff"`.
- `apps/dashboard/operad_dashboard/agent_routes.py` (extend) —
  add `GET /runs/{id}/agent/{path}/parameters` and
  `GET /runs/{id}/agent/{path}/diff?from=A&to=B`.

### Depends on

- 2-2 (edge popup), 2-3 (drawer registry).
- 1-3 (existing per-agent endpoints; you're adding to them).
- Operad's existing `Agent.diff()`, `state()`, and
  `named_parameters()` — you don't change operad core.

### Out of scope

- Editing parameters and re-running — 4-3 owns the
  experimentation flow.

---

## Vision

### Parameters panel (in the edge popup)

```
┌─ Parameters (3 trainable) ───────────────────────────────┐
│ role               TextParameter        "You are…"        │
│ task               TextParameter        "Score the…"      │
│ config.sampling.temperature  FloatParameter   0.7         │
└───────────────────────────────────────────────────────────┘
```

Each row:

- Path (e.g. `role`, `rules[2]`, `config.sampling.temperature`).
- Parameter type chip (TextParameter / FloatParameter /
  CategoricalParameter / etc.).
- Current value (truncated; click to expand inline).
- If a `.grad` exists (after a training step), show a small
  "grad" pill with the textual gradient message; click → opens
  drawer view "prompts" with the grad-as-rationale rendered
  inline, or a dedicated "gradients" view if you want.
- Constraint summary (e.g. "0.0 ≤ x ≤ 2.0", "vocab: gpt-4o-mini,
  gpt-4o, claude-3", "len ≤ 800 chars"). Hover for full
  constraint object.

If the agent isn't `mark_trainable`'d (no parameters opted in),
show a subtle empty state: "no trainable parameters · use
`agent.mark_trainable(role=True, task=True)` to enable".

### Invocation diff drawer view

User picks two invocations from the metadata table (2-1) — add a
"diff with..." selector — and the drawer opens at `kind: "diff"`
with payload `{agentPath, fromInvocationId, toInvocationId}`.

Renders the `AgentDiff` from the new endpoint:

```
┌─ MyAgent · diff between invocation #4 and #5 ─────────────┐
│  hash_content: 1a2b → c3d4                                │
├───────────────────────────────────────────────────────────┤
│  role         CHANGED                                     │
│    - "You are a thoughtful reasoner."                     │
│    + "You are a thoughtful, terse reasoner."              │
│                                                           │
│  rules        APPENDED                                    │
│    + "Avoid speculation."                                 │
│                                                           │
│  config.sampling.temperature  CHANGED                     │
│    - 0.9   →   + 0.3                                      │
└───────────────────────────────────────────────────────────┘
```

Where the change touches a Parameter, link to the parameters
panel; where it's a structural reshape (composite child added /
removed), render the structure clearly.

---

## Backend additions

### `GET /runs/{id}/agent/{path}/parameters`

```json
{
  "agent_path": "Root.stage_0",
  "parameters": [
    {
      "path":          "role",
      "type":          "TextParameter",
      "value":         "You are…",
      "requires_grad": true,
      "grad":          {"message": "...", "severity": 0.4} | null,
      "constraint":    {...} | null
    }
  ]
}
```

Walk `agent.named_parameters()`, filter to `requires_grad=True`.

### `GET /runs/{id}/agent/{path}/diff?from=A&to=B`

Compute `agent_state(A).diff(agent_state(B))` and return:

```json
{
  "from_invocation":  "...",
  "to_invocation":    "...",
  "from_hash_content": "1a2b...",
  "to_hash_content":   "c3d4...",
  "changes": [
    {"path": "role", "kind": "role",  "detail": "..."},
    {"path": "rules", "kind": "rules", "detail": "..."}
  ]
}
```

If state snapshots aren't captured per invocation today, capture
them at `invoke_end` time as part of the event metadata (small
operad-core change — `metadata["state_hash"]` already exists in
spirit; you may need to also persist the full snapshot for runs
in memory and load from archive otherwise).

If you change ingest behavior to capture state, document it in
this brief and in `INVENTORY.md` §1.

---

## Implementation pointers

- For the parameters panel, the `meta` endpoint from 1-3 already
  surfaces `trainable_paths`. Extend that or call the new
  parameters endpoint. Pick whichever yields a cleaner layout
  flow.
- Constraint rendering: the constraint Pydantic model has known
  shapes (`bounds`, `vocab`, `length`). Render each shape with a
  matching mini-renderer.
- For the diff renderer, do the textual-diff highlighting using
  the same diff library 3-2 brings in.
- Make sure the "diff with..." selector in 2-1 (metadata table)
  is available; add it as a row-action that puts the row's
  invocation into a "comparison slot" state, then a second click
  opens the drawer with both IDs.

---

## Polish targets

- The parameters panel becomes informationally rich for
  optimised agents but should also feel useful for un-trained
  agents (where it shows "0 parameters trainable" + a hint).
- The diff view should make `hash_content` deltas feel meaningful
  — show both hashes prominently up top.
- Where a change has a grad attached (from the parameters
  panel), surface "this change came from gradient X" — links the
  optimization story together.

---

## Be creative

- A "lineage view" that traces every change in `hash_content`
  across an entire run, not just one pair of invocations. Useful
  for agents inside a `Trainer.fit` loop.
- Visualise constraints as bounded ranges (sliders) so users
  see at a glance how close the parameter is to its constraint
  edge.
- Diff "explain" mode: when a change includes a Parameter, link
  to the gradient that produced it (would need
  `gradient_log` events from `Trainer.fit` — already exist as
  "gradient" envelopes).

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
uv run pytest apps/dashboard/tests/ -q
make dashboard && make dev-frontend
# With a trained agent run (e.g. an EvoGradient run), open an agent
# edge popup → the Parameters section renders rows with grad and
# constraint info. Pick two invocations from the metadata table
# → "diff with..." → drawer opens at kind="diff" with the changes
# rendered.
```
