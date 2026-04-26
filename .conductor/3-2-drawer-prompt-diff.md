# 3-2 Drawer view: prompt diff across invocations

## Scope

The killer feature for prompt-engineering workflows: a drawer view
that shows the *rendered prompts* across every invocation of an
agent path, with diff highlighting between consecutive
invocations and a "drift jump" navigator that lands you on the
exact transition where the prompt changed.

### You own

- `apps/frontend/src/components/agent-view/drawer/views/prompts/`
  - `prompt-diff.tsx` — the main drawer view.
  - `prompt-renderer.tsx` — renders one prompt with system/user
    structure (XML / markdown / chat tabs).
  - `prompt-pair-diff.tsx` — side-by-side or inline diff between
    two prompts.
  - `drift-navigator.tsx` — top bar with "<< prev drift / next
    drift >>" plus an inline mini-version of the drift strip from
    2-4 (reuse it if you can).
  - `index.ts` — registers `"prompts"`.

### Depends on (iter-1 contracts)

- `GET /runs/{id}/agent/{path}/prompts` (1-3) — array of rendered
  prompts.
- `registerDrawerView` (2-3).
- The drift-strip / hash-color helper from 2-4 (export it and
  reuse).

### Out of scope

- Triggering edits to prompts and re-running — that's 4-3.
- Storing rendered prompts; assume the endpoint handles caching.

---

## Vision

A user clicks "Prompt" on an agent edge, or clicks a drift-strip
transition. The drawer slides in. They see:

```
┌─ Drift navigator ─────────────────────────────────────────┐
│  << prev drift  ░▓░▒░▓░▓░▒░▒░  next drift >>             │
│  showing invocation #42 vs #43  ·  hash 9a9b → c1c2       │
├───────────────────────────────────────────────────────────┤
│  [ system ]  [ user ]   ←  tab toggle                     │
│                                                           │
│  - You are a thoughtful reasoner...                       │
│  + You are a thoughtful reasoner. Be terse.               │
│                                                           │
│  Rules:                                                   │
│  - Never exceed 20 words                                  │
│  + Never exceed 20 words                                  │
│  + Avoid speculation                                      │
└───────────────────────────────────────────────────────────┘
```

- The mini drift strip lets the user jump to any transition.
- Two view modes: **side-by-side diff** (comparing N to N+1) and
  **single prompt** (just render one invocation's prompt verbatim
  in the chosen renderer).
- Tabs to switch renderer (xml / markdown / chat) when the agent
  supports it. The endpoint returns a single rendered shape
  (whatever the agent's config says), but optionally we can
  expand later — for v1, render whatever the endpoint sends.
- "Copy as Markdown" and "Open in Langfuse" actions in the
  toolbar.

When the payload includes `focus: invocationId`, scroll the diff
to the appropriate transition.

---

## Implementation pointers

- For the diff, use [`diff`](https://github.com/kpdecker/jsdiff)
  or a similar lightweight library. Word-level diff for system
  messages, line-level for rules and examples.
- The endpoint returns the system+user split per invocation; show
  them in tabs and let the user toggle.
- The drift navigator should reuse the *exact same* color/shape
  language as 2-4's `DriftStrip`. Don't fork it; export the
  primitive.
- Cache the prompts payload by `(runId, agentPath)` — they're
  expensive to recompute server-side.
- For chat-rendered prompts (list of `{role, content}` dicts),
  show each turn as a card; diff is per-turn.
- Render system prompts in a monospace block; preserve XML tags
  with subtle syntax color.

---

## Polish targets

- The "no drift detected" state: when all invocations share the
  same `hash_prompt`, show a single prompt view + a friendly note
  "the prompt has been stable across 17 invocations".
- Long prompts: collapsible sections by tag (`<role>`, `<task>`,
  `<rules>`, `<examples>`). Each section has its own
  expand/collapse.
- Inline diff vs side-by-side toggle.
- Show the input that produced this prompt — sometimes the prompt
  changed because the input changed (the per-call system input
  from `_compose_system_for_call`). Make this transparency
  legible.

---

## Be creative

- "Promote this prompt" — a button that copies the rendered
  system+user as a self-contained snippet (for sharing with
  colleagues, pasting into the playground, etc.).
- A small "why did this change?" footnote when the diff includes
  fields that map to a `Parameter` (e.g. role, rules) — link it
  to the trainable-parameters panel (4-2).
- The diff can highlight which sections of the prompt changed
  most across the entire run, not just consecutive invocations
  ("rules changed 4 times, role changed 1 time, examples never").

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
make dashboard && make dev-frontend
# Open an agent run with at least 3 invocations on the same agent
# path. Trigger the prompts drawer.
# - Diff renders for invocation 1 vs 2.
# - Drift navigator advances to next drift.
# - Single-prompt mode shows the rendered prompt verbatim.
# - Copy-as-markdown and open-in-langfuse work.
```
