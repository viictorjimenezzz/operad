# 4-3 Inline experimentation: run-this-example + edit-and-re-invoke

## Scope

Make the agent view *interactive*. Two complementary affordances:

1. **Run this example** — every row in the `examples` array on
   an agent (and every historic invocation) gets a "re-run"
   button that fires the live agent against that input and
   appends the result.
2. **Edit and re-invoke** — open an agent edge popup, edit
   `role` / `task` / `rules` / `examples` inline, click "run", and
   see the result of the *modified* agent on a chosen input. The
   modification is ephemeral (does not persist on the live agent
   tree) but tagged with a `hash_content` so it lines up with the
   fingerprint card and drift strip.

### You own

- `apps/frontend/src/components/agent-view/drawer/views/experiment/`
  - `experiment-runner.tsx` — main drawer view.
  - `prompt-editor.tsx` — editable role/task/rules/examples form.
  - `invoke-button.tsx` — POSTs to the new endpoint with
    progress / streaming display.
  - `result-card.tsx` — renders the ephemeral
    OperadOutput envelope.
  - `index.ts` — registers `"experiment"`.
- `apps/frontend/src/components/agent-view/insights/` — add a
  "run this example" affordance to existing example chips.
- `apps/dashboard/operad_dashboard/agent_routes.py` (extend) —
  new `POST /runs/{id}/agent/{path}/invoke` endpoint.

### Depends on

- 2-1, 2-2, 2-3, 2-4, 3-2 — every drawer view + popup
  primitive. This is the iteration's most advanced stream.

### Out of scope

- Persisting changes to the underlying agent. The endpoint
  uses `agent.clone()` + state mutation, runs once, and discards.
- Building a full prompt-engineering IDE.

---

## Vision

The agent view becomes a *scratchpad*. A user reading the prompt
diff in 3-2 spots a phrasing they'd improve. They click "edit and
run" on the agent edge popup. The drawer flips to the
experiment view with the current `role` / `task` / `rules` /
`examples` pre-populated. They tweak a rule. They pick an input
from the historic invocations dropdown ("question: 'what is the
capital of France?'"). They click "run". A second later, the
ephemeral result appears in the drawer — alongside the original
result and a structural diff.

This is the closest the dashboard gets to the optim-side machinery.
It demonstrates operad's `clone()` + `state()` machinery to the
user as a UX, not just an API.

---

## Backend addition

### `POST /runs/{id}/agent/{path}/invoke`

Body:

```json
{
  "input":   {<input fields>},
  "overrides": {            // optional; if omitted, runs the live agent unchanged
    "role":     "...",
    "task":     "...",
    "rules":    ["...", "..."],
    "examples": [...],
    "config":   {...}        // partial; merged into the live config
  },
  "stream": false             // for v1, no SSE — just a single envelope back
}
```

Response: the full `OperadOutput` envelope, JSON-serialised, with
`metadata["experiment"] = true` so the dashboard knows not to
treat this as a "real" invocation.

Implementation:

- `clone()` the agent at `path` from the live tree.
- If overrides present, mutate the clone via `load_state()` or
  field-by-field assignment.
- Re-build (`abuild()`).
- Invoke against the supplied input.
- Return the envelope. Don't append to the run's event buffer
  (or append with a clear "experiment" tag — your call, but be
  consistent).

If the agent's input model can't construct from the supplied
fields (validation error), return 400 with a clear message and
the offending field.

### Safety

- Add a server-side opt-in: the endpoint is enabled iff the
  dashboard is launched with `--allow-experiment` or env
  `OPERAD_DASHBOARD_ALLOW_EXPERIMENT=1`. Users in
  observability-only deployments shouldn't accidentally fire
  model calls.
- Capture the experiment in a separate "experiments" log file
  (NDJSON) for audit.

---

## Frontend

### Experiment drawer view

Three sections:

1. **Edit panel** — form fields for role / task / rules /
   examples / sampling.temperature. Preserves the agent's
   current values as defaults. Mark dirty fields with a "*".
2. **Input picker** — radio: "use historic input" (dropdown of
   recent invocations) or "type my own" (JSON editor seeded with
   the input schema's fields).
3. **Run / result** — when "run" is pressed, the result card
   shows: latency, token counts, `hash_content` of the
   experiment, structural diff vs. the live agent (reuse 4-2's
   diff renderer), and the rendered output. If the user runs
   multiple times, stack results most-recent-first.

### Run-this-example button

On every example chip in the metadata header (2-1) and on every
row in the invocations table:

- Adds a "run again" icon-button.
- Click → opens experiment drawer pre-populated with that
  example's input and *no* overrides (i.e. just re-run on the
  live agent).
- The result appears in the same drawer's run-result section.

---

## Implementation pointers

- Use a controlled form for the edit panel (React Hook Form is
  fine; no need to over-engineer).
- For the JSON editor, `@uiw/react-json-view` editable mode or a
  small CodeMirror config. Validate against the input schema's
  zod-from-pydantic shape if you can derive one.
- Stream support is "no" for v1 — keep the request simple. We
  can SSE later.
- The endpoint should respect rate limits + retry config from
  the agent's `Configuration.resilience`. Make sure errors come
  back legibly.

---

## Polish targets

- A "compare" toggle that runs the live agent and the
  experiment side by side (two requests in parallel) and shows
  diffs of both outputs and both `hash_content`s.
- "Save experiment" — store the override + result in the
  archive's experiments log so users can compare across sessions.
- Rate-limit the experiment button (no double-clicks, show
  inline "running…" state).
- Handle large outputs (chunked rendering) and timeouts (clear
  error UI).

---

## Be creative

- This is the demo-able feature. If you can also include a
  "promote to commit" affordance — copying the experiment's
  overrides into a snippet that the user can paste into their
  agent definition — do it. It closes the loop between
  observation and code change.
- Show the experiment's `hash_content` on the live drift strip
  (2-4) at the time it ran, in a different style (e.g. dotted
  border) so users can see "I tried this; here's where it would
  land".
- The drawer's "experiment" entry could itself be saved into a
  per-run "scratchpad" log so users build up an experiment
  history across a debugging session.

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
uv run pytest apps/dashboard/tests/ -q
OPERAD_DASHBOARD_ALLOW_EXPERIMENT=1 make dashboard
make dev-frontend
# With a live agent run open:
# - Click an example chip → experiment drawer pre-populates with
#   that input; "run" returns an envelope, rendered.
# - Open an agent edge popup → "edit and run" → modify a rule →
#   pick an input → run → result card shows envelope + diff.
# - Spam-clicking is debounced; large outputs render without
#   freezing the UI.
```
