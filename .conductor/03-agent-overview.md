# 03 — Single-invocation Overview redesign

**Stage:** 3 (parallel; depends on Briefs 01, 02)
**Branch:** `dashboard-redesign/03-agent-overview`
**Depends on:** Brief 01 (RunTable, CollapsibleSection, hashColor),
Brief 02 (route shape, tab system, AgentRunDetailLayout)

## Goal

Redesign the page at `/agents/:hash/runs/:runId` so it stops dumping six
redundant cards in your face. The page now serves one purpose: *show me
this specific invocation, fast*. Smaller preview, expand for detail.
Replace four-card "Definition" with one collapsible section. Drop the
"Latest invocation" eyebrow. Add a Metrics tab that actually shows
metrics. Make the Graph tab work for single-leaf agents.

This brief redesigns the **single-invocation** flow only. Brief 04
handles the **group** flow.

## Read first

- Your route: `/agents/:hash/runs/:runId`. Layout owner is
  `AgentRunDetailLayout` (Brief 02 created it).
- `proposal.md` §3.3 — the design intent.
- `apps/frontend/src/components/agent-view/overview/` — every block
  here is fair game to keep, redesign, or delete:
  - `identity-block.tsx` — keep, redesign as flat (no PanelCard chrome).
  - `backend-block.tsx` — keep, fold under a single Definition section.
  - `config-block.tsx` — keep, fold.
  - `examples-block.tsx` — keep, fold.
  - `trainable-params-block.tsx` — keep but moves to Train tab on
    single invocation, *NOT* shown on Overview (parameter values are
    visible in the agent body proper).
  - `cost-latency-block.tsx` — DELETE (replaced by per-invocation
    Metrics tab).
  - `drift-block.tsx` — keep but only renders on Drift tab.
  - `reproducibility-block.tsx` — keep, fold.
  - `sister-runs-block.tsx` — replaced by a "back to group" CTA in the
    chrome.
  - `invocations-banner.tsx` — `SingleInvocation` is gone (Brief 01).
  - `latest-invocation-card.tsx` — DELETE (orphan).
  - `io-field-preview.tsx` — KEEP, becomes the page's hero.
  - `invocations-list.tsx` — keep, but Brief 02 already removed the
    Invocations tab from this rail.
- `apps/frontend/src/layouts/agent/overview.json` — the static JSON
  layout that today is shared between group and single-invocation. We
  split it: this brief replaces it for single-invocation.
- `00-CONTRACTS.md` §2.3 (`CollapsibleSection`), §4.2 (Run summary now
  carries `metrics: dict[str, float]` and `notes_markdown: str`),
  §6 (URL state).
- `INVENTORY.md` §3 (the envelope's reproducibility fingerprint), §13
  (langfuse_url surfacing), §20 (hash family), §21 (Parameter family
  in case the Train tab cross-references this page).

## Files to touch

Create:

- `apps/frontend/src/dashboard/pages/run-detail/SingleInvocationOverviewTab.tsx`
- `apps/frontend/src/dashboard/pages/run-detail/SingleInvocationGraphTab.tsx`
  (thin: imports `GraphPage`, no other change)
- `apps/frontend/src/dashboard/pages/run-detail/SingleInvocationMetricsTab.tsx`
- `apps/frontend/src/dashboard/pages/run-detail/SingleInvocationDriftTab.tsx`
  (thin: renders `DriftBlock` if drift events exist, else 404)
- `apps/frontend/src/components/agent-view/overview/io-hero.tsx`
  (the new big I/O preview that hosts the page)
- `apps/frontend/src/components/agent-view/overview/definition-section.tsx`
  (one CollapsibleSection containing Identity / Backend / Config /
  Examples)
- `apps/frontend/src/components/agent-view/overview/run-status-strip.tsx`
  (the slim KPI strip that opens the page)
- `apps/frontend/src/components/agent-view/overview/notes-section.tsx`
  (Markdown notes, edit on click)
- `apps/frontend/src/layouts/agent/single-invocation-overview.json`
  (the new layout for the single-invocation Overview)
- `apps/frontend/src/layouts/agent/single-invocation-metrics.json`
  (the new Metrics tab)

Edit:

- `apps/frontend/src/components/agent-view/overview/identity-block.tsx`
  — strip `PanelCard` chrome; expose a "flat" mode where it returns the
  inner content without an outer card.
- `apps/frontend/src/components/agent-view/overview/backend-block.tsx`
  — same flat-mode option.
- `apps/frontend/src/components/agent-view/overview/config-block.tsx`
  — same.
- `apps/frontend/src/components/agent-view/overview/examples-block.tsx`
  — same.
- `apps/frontend/src/components/agent-view/overview/reproducibility-block.tsx`
  — same; this is the Reproducibility CollapsibleSection's body.
- `apps/frontend/src/layouts/agent/overview.json` — DELETE (split into
  the two new files).
- `apps/frontend/src/dashboard/pages/run-detail/OverviewTab.tsx` —
  DELETE (replaced by `SingleInvocationOverviewTab`).
- `apps/frontend/src/dashboard/pages/run-detail/GraphTab.tsx` — DELETE
  (replaced; uses the same inner `GraphPage`).
- `apps/frontend/src/dashboard/pages/run-detail/InvocationsTab.tsx` —
  DELETE (no longer a tab on this rail).
- `apps/frontend/src/dashboard/pages/run-detail/TrainTab.tsx` — DELETE
  (no longer a tab on the single-invocation page; group page owns it).
- `apps/frontend/src/dashboard/pages/run-detail/CostTab.tsx` — DELETE
  (already replaced by Brief 02 with Metrics).
- `apps/frontend/src/components/agent-view/overview/cost-latency-block.tsx`
  — DELETE.
- `apps/frontend/src/components/agent-view/overview/sister-runs-block.tsx`
  — DELETE (the "back to group" CTA in the chrome supersedes it).
- `apps/frontend/src/components/agent-view/overview/latest-invocation-card.tsx`
  — DELETE.

## Page anatomy

```
─── breadcrumb chrome (Brief 02 owns; we just consume) ───
Agents › Reasoner › 62af09c…              [● ended]  [langfuse]

─── slim run status strip (canvas-resident) ────────────
[ ● ok ]  hash 9dfd19a942…  [ ended ]   1.4s   312 + 198 tokens   $0.0042

─── I/O hero (the only thing big on the page) ─────────
┌── Input ───────────────────────┐  ┌── Output ──────────────────────┐
│ {                              │  │ {                              │
│   "text": "Why is the sky..."  │  │   "text": "The sky is blue..." │
│ }                              │  │ }                              │
└────────────────────────────────┘  └────────────────────────────────┘

─── notes (Markdown) ──────────────────────────────────
▸ Notes (empty) — click to add a note  ✎

─── collapsible sections ──────────────────────────────
▸ Definition (Reasoner · openai/gpt-4o-mini · temp 0.4)            ⌄
▸ Reproducibility (7 hashes; 2 changed since the previous run)     ⌄
```

Sections expand on click. URL hash `#section=<id>` opens the matching
section on load.

## Component-by-component

### `RunStatusStrip`

Replaces the chrome's right-side KPI block (Brief 02 keeps the chrome
slim — breadcrumb + state pill + langfuse link only). The status strip
sits at the top of the canvas:

```
[● ok | err] [hash chip]  [state pill] [latency] [tokens in/out] [cost]
```

Each metric is a `Metric` primitive (existing). Clicking the hash chip
copies it to the clipboard. Clicking the state pill opens the **back
to group** popover with a list of sibling invocations and a button
"View all invocations" → `/agents/:hash/runs`.

### `IOHero`

Two-column `IOFieldPreview` (existing component) at full width, both
cards default-expanded. Below the cards, a small toolbar:

- "Copy as JSON" button (clipboard).
- "Replay" button — disabled unless `allow_experiment` is true on the
  manifest. When enabled, posts to
  `/runs/:runId/agent/:rootAgentPath/invoke` (existing) and renders the
  result as a `<details>` "replay result" block beneath. The replay
  feature is the inventory's "Edit & run" capability surfaced as a
  first-class action.
- "Cassette replay" button — present when the user passes the env var
  `OPERAD_CASSETTE` (the manifest exposes whether cassette mode is
  active). Visible but disabled with a tooltip when not active.

### `NotesSection`

`MarkdownView` + `MarkdownEditor` (Brief 01). Pulls
`summary.notes_markdown` from the run summary. Saves via
`PATCH /api/runs/:id/notes`. When empty, the section header shows
"add a note" with a tiny pencil; clicking opens the editor inline.

### `DefinitionSection` (the collapsible card replacing 4 cards)

One `CollapsibleSection` titled "Definition". The preview slot reads:

```
{class_name} · {backend}/{model} · temp {temperature}
```

Body uses a 4-row stack (no inner panel borders):

```
[Identity (flat)]
   role · task · rules · examples count
[Backend & sampling (flat)]
   backend · model · host · sampling
[Configuration (flat)]
   sampling, resilience, io
[Examples (flat)] (renders only if examples.length > 0)
   first 3 examples; "view all (N)" link
```

This is one section, one chrome, four sub-blocks. The visual repetition
issue from `proposal.md` §6.1 is resolved by removing four PanelCards
and using subtle dividers between sub-blocks.

### `ReproducibilitySection`

`CollapsibleSection` titled "Reproducibility". Preview reads:

```
hash_content {hash:8} · 7 hashes · {N} changed since previous
```

Body is the existing `ReproducibilityBlock` (flat mode). Each hash row:

```
hash_content       9dfd19a9423a8113   [chip with hashColor swatch]
hash_prompt        ce1488…            [diff vs previous if changed]
hash_input         11223344…
hash_output_schema c0ffee01…
hash_graph         deadbeef…
hash_model         abcd1234…
hash_config        ffffffff…
```

When any hash changed since the previous invocation in the same group,
flag with a `[changed]` `Pill tone="warn"` and a tooltip showing the
previous value. This is the inventory §20 fingerprint surfaced as
*meaningful* drift signal.

### `SingleInvocationMetricsTab` (replaces Cost)

Per `00-CONTRACTS.md` §4.1, `RunSummary` now carries
`metrics: dict[str, float]`. Render a `RunTable`-style table of:

```
Metric                          Value         Δ vs group p50
─────────────────────────────────────────────────────────────
latency_ms                      1,420         +12% (p50 1,267)
prompt_tokens                   312           -3%
completion_tokens               198           +0%
cost_usd                        $0.0042       +12%
exact_match (custom)            1.000         +25% vs group p50
length_band (custom)            0.78          -8%
```

The "Δ vs group p50" column is computed client-side: fetch
`/api/agents/:hash/metrics` (Brief 14 endpoint), compute the median per
metric, color the delta cell with `--color-ok`/`--color-warn`/`--color-err`
based on directionality. Q2 answer = yes, this column is the unique
single-invocation analytical view.

When the run only has one invocation (group size 1), the Δ column is
hidden because there's nothing to compare against.

### `SingleInvocationDriftTab`

Renders `DriftBlock` if `useDrift(runId).data.length > 0`. Otherwise
renders `EmptyState` and the route condition (Brief 02 §`condition`)
hides the tab from the strip in the first place. So this tab body is
mostly just `<DriftBlock dataInvocations={…} runId={runId} />`.

### `SingleInvocationGraphTab`

Mounts `<GraphPage runId={runId} />` from
`apps/frontend/src/components/agent-view/graph/graph-page.tsx`. The
single-leaf rendering fix is in Brief 01 (`AgentFlowGraph`); nothing to
do here beyond the wrapper.

## JSON layouts

`apps/frontend/src/layouts/agent/single-invocation-overview.json`:

```json
{
  "algorithm": "agent.single-invocation.overview",
  "version": 1,
  "dataSources": {
    "summary": { "endpoint": "/runs/$context.runId/summary" },
    "invocations": { "endpoint": "/runs/$context.runId/invocations" },
    "groupMetrics": { "endpoint": "/api/agents/$queries.summary.hash_content/metrics" }
  },
  "spec": {
    "root": "page",
    "elements": {
      "page": {
        "type": "Stack",
        "props": { "gap": 16 },
        "children": ["status", "io", "notes", "definition", "repro"]
      },
      "status": { "type": "RunStatusStrip", "props": {
        "sourceSummary": "$queries.summary",
        "sourceInvocations": "$queries.invocations",
        "runId": "$context.runId"
      }},
      "io": { "type": "IOHero", "props": {
        "sourceInvocations": "$queries.invocations"
      }},
      "notes": { "type": "NotesSection", "props": {
        "sourceSummary": "$queries.summary",
        "runId": "$context.runId"
      }},
      "definition": { "type": "DefinitionSection", "props": {
        "sourceSummary": "$queries.summary",
        "runId": "$context.runId"
      }},
      "repro": { "type": "ReproducibilitySection", "props": {
        "sourceInvocations": "$queries.invocations"
      }}
    }
  }
}
```

`apps/frontend/src/layouts/agent/single-invocation-metrics.json`:

```json
{
  "algorithm": "agent.single-invocation.metrics",
  "version": 1,
  "dataSources": {
    "summary": { "endpoint": "/runs/$context.runId/summary" },
    "invocations": { "endpoint": "/runs/$context.runId/invocations" },
    "groupMetrics": { "endpoint": "/api/agents/$queries.summary.hash_content/metrics" }
  },
  "spec": {
    "root": "page",
    "elements": {
      "page": { "type": "Stack", "props": { "gap": 16 }, "children": ["table"] },
      "table": { "type": "MetricsValueTable", "props": {
        "sourceSummary": "$queries.summary",
        "sourceInvocations": "$queries.invocations",
        "sourceGroupMetrics": "$queries.groupMetrics",
        "runId": "$context.runId"
      }}
    }
  }
}
```

`MetricsValueTable` is a new wrapper component you create in this
brief (`apps/frontend/src/components/agent-view/overview/metrics-value-table.tsx`).

## Design alternatives

### A1: How to fold the four Definition cards

- **(a)** One `CollapsibleSection` containing four flat sub-blocks
  (recommended).
- **(b)** A `Tabs` element inside the section with sub-tabs Identity /
  Backend / Config / Examples. **Reject:** doubles the click cost; the
  user wants *less* navigation, not more.
- **(c)** A `KeyValueGrid` flattening every field into one giant table.
  **Reject:** loses semantic grouping.

### A2: Where to put the "Replay" / experiment button

- **(a)** Inline in the I/O hero toolbar (recommended). Discoverable,
  next to the inputs the user is reading.
- **(b)** In the breadcrumb chrome's right actions slot. **Reject:**
  the chrome should stay slim.
- **(c)** Hidden behind a kebab on each I/O panel. **Reject:** too
  hidden for an experiment-mode-only feature that we want users to
  discover.

### A3: Notes editor location

- **(a)** Section between I/O and Definition (recommended). Notes are
  about *this* invocation; they sit next to its I/O.
- **(b)** Sidebar drawer. **Reject:** too far from context.
- **(c)** In the breadcrumb chrome. **Reject:** rebreaks the slim chrome
  promise.

### A4: Metrics tab — table or chart

- **(a)** Table with Δ-vs-group column (recommended; matches §3.3 of
  the proposal).
- **(b)** Charts (one per metric) with a "you are here" highlight. The
  *group* page does this in Brief 04; for a single invocation, a table
  is denser.

## Acceptance criteria

- [ ] `/agents/:hash/runs/:runId` shows a slim status strip, then
  large I/O preview, then notes, then a single Definition collapsible,
  then a single Reproducibility collapsible. *No* "Latest invocation"
  text anywhere.
- [ ] No Invocations tab and no Train tab on this rail.
- [ ] No Cost tab; Metrics tab in its place.
- [ ] Definition section's preview reads
  `<class> · <backend>/<model> · temp <temp>` and the body shows
  Identity / Backend / Config / Examples without per-card chrome.
- [ ] URL `#section=definition` opens that section by default.
- [ ] Notes section renders Markdown; clicking the pencil opens an
  inline editor; saving PATCHes `/api/runs/:id/notes`; the new text
  shows up after save without a page reload.
- [ ] Metrics tab renders a table with built-in metrics + any custom
  metrics on `summary.metrics`. Δ-vs-group column shows when the
  group has ≥2 invocations.
- [ ] Drift tab is hidden when no drift events; renders the existing
  `DriftBlock` when present.
- [ ] Graph tab renders single-leaf agents (Reasoner-only) using the
  Brief 01 fix (one node centered).
- [ ] Reproducibility section flags hashes that changed since the
  previous invocation in the same group (queried via
  `/runs/:id/invocations`).
- [ ] No `latest-invocation-card.tsx`, `cost-latency-block.tsx`,
  `sister-runs-block.tsx`, or `cost-tab.tsx` exists in the codebase.
- [ ] `pnpm test --run` green; `make build-frontend` green.
- [ ] Manual smoke against examples 01 (multi-leaf) and 03 (single-
  leaf with trainable param) passes.

## Test plan

- **Unit:** `single-invocation-overview-tab.test.tsx` covers status
  strip, definition collapsing/expanding, notes save flow.
- **Layout schema:** snapshot test for the new JSON files.
- **Component:** `definition-section.test.tsx` ensures all four
  sub-blocks render in flat mode with no nested PanelCard chrome.
- **Visual:** capture a before/after screenshot in the PR body.
- **Integration:** route test `agent-run-detail.test.tsx` ensures the
  tab strip matches the new shape (Overview / Graph / Metrics / Drift?).

## Out of scope

- The agent group page (Brief 04).
- Tab strip wiring and the `AgentRunDetailLayout` shell (Brief 02).
- Backend metric endpoint implementation (Brief 14).
- The `Replay` button's experiment-resolver backend (already exists in
  `agent_routes.py:598`).
- Drift visualization redesign (Brief 04 owns Train; Drift is reused
  here as-is).
- Compare drawer (Q3 — skip).

## Hand-off

PR body must include:
1. Acceptance-criteria checklist with file:line evidence.
2. Before/after screenshot of `/agents/:hash/runs/:runId` for example
   03's run (chosen because it has both a custom metric and trainable
   param coverage).
3. Confirmation that `latest-invocation-card.tsx` and friends are
   deleted (search `git log --diff-filter=D`).
4. Note any places where Brief 04 (group page) needs to expose data
   that Brief 03 consumes (`/api/agents/:hash/metrics` is the only
   one).
