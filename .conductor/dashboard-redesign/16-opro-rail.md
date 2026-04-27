# 16 — OPRO own page (Q7)

**Stage:** 4 (depends on Brief 14 for OPRO emit; Brief 02 for routing)
**Branch:** `dashboard-redesign/16-opro-rail`

## Goal

Q7 = "Add events and make its own page." OPRO is currently invisible
to the dashboard because it emits no events. Brief 14 makes OPRO emit a
proper algorithm lifecycle. This brief gives it a first-class home: a
new top-level rail at `/opro` with an algorithm-specific layout that
makes OPRO's parameter-rewrite history readable. OPRO runs that fire
inside `Trainer.fit()` are still discoverable as nested children of the
parent training run, but they have their own canonical view.

## Read first

- `00-CONTRACTS.md` §5.3 (the OPRO event shape that lands via Brief
  14), §9 (route map).
- Brief 14 — the OPRO emit implementation (`session()` + per-step
  `propose` / `evaluate` iteration events).
- `operad/optim/optimizers/opro.py` — the optimizer's logic.
- `apps/dashboard/operad_dashboard/routes/groups.py` — `GET /api/algorithms`
  excludes Trainer; for OPRO we want them visible *both* in
  `/api/algorithms` (when standalone) AND under their parent Trainer's
  children.
- `apps/dashboard/operad_dashboard/routes/iterations.py` — already
  picks up OPRO's `iteration` events without changes.
- `apps/frontend/src/components/panels/global-rail.tsx` — global rail
  navigation (we add an OPRO entry).
- `INVENTORY.md` §21 (Optimizer fleet — OPRO context, alongside TGD,
  Momentum, EvoGradient, APE).

## Files to touch

Create:

- `apps/frontend/src/dashboard/pages/OPROIndexPage.tsx` (Brief 02
  created the import stub).
- `apps/frontend/src/layouts/opro.json`.
- `apps/frontend/src/components/algorithms/opro/` (new):
  - `index.ts`
  - `registry.tsx`
  - `opro-detail-overview.tsx`
  - `opro-history-tab.tsx`
  - `opro-candidates-tab.tsx`
  - `opro-parameter-tab.tsx`

Edit:

- `apps/frontend/src/components/panels/global-rail.tsx` — add the OPRO
  rail icon (small flask or beaker — choose from `lucide-react`).
- `apps/frontend/src/components/panels/section-sidebar/section-sidebar.tsx`
  — add `path.startsWith("/opro")` rail detection.
- `apps/frontend/src/components/panels/section-sidebar/` — add
  `opro-tree.tsx` (analogous to `algorithms-tree.tsx`, queries
  `/api/algorithms?path=OPRO`).
- `apps/frontend/src/hooks/use-runs.ts` — add `useOPRORuns()` hook.
- `apps/dashboard/operad_dashboard/routes/groups.py` — add a small
  `/api/opro` endpoint (alias to `algorithms` filtered by
  `algorithm_path == "OPRO"`).
- `apps/frontend/src/components/algorithms/registry.tsx` — register
  the opro sub-registry.

## Index `/opro`

```
─── KPI strip ────────────────────────────────────
 17 OPRO sessions   3 currently active   best score 0.91
 total proposals: 142   acceptance rate: 32%

─── sessions table (RunTable) ────────────────────
[●●][State][Param targeted][hash][# proposals][# accepted][best score][last seen][cost][sparkline]
[●●][live ][rules         ][9dfd][12         ][4          ][0.84      ][live    ][$0.02][▁▂▃▆ ]
…
```

The "Param targeted" column is a comma-separated list of param paths
the session optimized.

Click a row → `/opro/:runId`. Multi-select disabled.

## Detail page `/opro/:runId`

Tabs:

```
[ Overview ] [ History ] [ Candidates ] [ Parameter ] [ Agents ] [ Events ] [ Graph ]
```

### Overview

```
─── status strip ──────────────────────────────────
[ ● ended ]  param  rules  steps 12  accepted 4
best score 0.84   total cost $0.018   wall 4m 12s

─── score history (line chart) ────────────────────
x = step_index, y = score, accepted points filled, rejected hollow.
Best-so-far line overlaid.

─── headline candidate (the best accepted) ────────
"<the candidate text that won — Markdown>"
score 0.84   accepted at step 7
[ Open evaluator's run → /agents/:hash/runs/:eval_runId ]

─── parent context (when nested in a Trainer) ─────
"This OPRO session ran inside Trainer run 7f3a· ; epoch 3, optimizer step 7 of 12."
[ Open Trainer run → /training/:trainerRunId ]
```

### History (the marquee tab)

A vertical timeline of `(propose → evaluate)` pairs. Each pair is one
card:

```
─── step 7 ───────────────────── score 0.84  ✓ accepted ─
proposed:
  "Write a clear, factual answer in 3-5 sentences (200-450 chars)."
history at proposal time (8 entries):
  - "Write a clear answer..." (0.51)
  - "Write a clear, factual answer..." (0.62)
  - …
[ Open proposer's invocation → /agents/:hash/runs/:opro_agent_runId ]
[ Open evaluator's invocation → /agents/:hash/runs/:eval_runId ]

─── step 8 ───────────────────── score 0.71  ✗ rejected ─
proposed:
  "..."
[…]
```

Accepted vs rejected pills color-coded. URL `?step=N` deep-links.

### Candidates

A `RunTable` of all candidates seen, sortable by score. Columns:

```
[●][Step][Status][Score][Candidate text preview][Param][Length][Cost]
```

Status pill: `accepted` (ok), `rejected` (warn). Text preview is
Markdown-rendered, 80 chars truncated.

### Parameter

Cuts at the *parameter* axis: one section per `param_path` showing
that parameter's evolution within this OPRO session. Reuses
`ParameterEvolution` from Brief 04 / Brief 13 (the lane chart of
distinct values). Click a value cell → `MultiPromptDiff` against the
previous accepted value.

### Agents

Universal. Synthetic children = OPRO-agent (the proposer) + the
evaluator. Default `groupBy: "hash"` collapses cleanly.

### Events / Graph

Universal.

## Cross-rail linking

OPRO sessions that ran inside `Trainer.fit()` have
`parent_run_id == trainer_run_id`. Brief 13's Trainer detail page
already lists synthetic children in the Agents tab; an OPRO session
appears there as a child run — clicking it should land on
`/opro/:runId` (not the agent rail). Brief 13 + Brief 15 should
recognize children with `algorithm_path == "OPRO"` and route to the
OPRO rail; coordinate via this brief's PR.

## Design alternatives

### A1: OPRO as own rail vs. nested under Algorithms

- **(a)** Own rail at `/opro` (recommended; Q7 = "make its own page").
- **(b)** Just include OPRO under `/algorithms`. **Reject:** the user
  explicitly asked for an own page.
- **(c)** Both: OPRO appears in the global rail AND in the algorithms
  index. Acceptable if visual noise is contained; default to (a) for
  cleanliness.

### A2: History as ladder vs. table

- **(a)** Ladder of cards (recommended; story shape — propose, then
  reveal score).
- **(b)** Pure table. The Candidates tab covers the table view.

### A3: Should APE / TGD / Momentum get their own rails too?

- **No** for this redesign cycle. Q7 only specified OPRO. APE and
  TGD currently emit *less* than OPRO will after Brief 14; they aren't
  surfaced as separate algorithms in `/api/algorithms`. If the user
  later wants them surfaced, mirror this brief.

## Acceptance criteria

- [ ] Global rail icon for OPRO present and clickable.
- [ ] `/opro` shows the index `RunTable`.
- [ ] `/opro/:runId` shows the seven-tab layout.
- [ ] Overview surfaces the score history line chart with accepted vs
  rejected markers, the best-candidate card, and the parent-Trainer
  cross-link when applicable.
- [ ] History tab shows propose→evaluate step cards with deep-links to
  proposer and evaluator runs.
- [ ] Candidates tab is sortable; storage key `opro-candidates:<runId>`.
- [ ] Parameter tab shows lane evolution + diff panel.
- [ ] OPRO sessions nested under a Trainer correctly cross-link from
  the Trainer's Agents tab to `/opro/:runId`.
- [ ] `pnpm test --run` green; backend tests for the OPRO emit (Brief
  14) green.
- [ ] Manual smoke: rerun `examples/03_training.py` after Brief 14
  lands; observe a new OPRO session appearing in the OPRO rail and
  cross-linking from the Trainer.

## Test plan

- **Unit:** `opro-history-tab.test.tsx`, `opro-candidates-tab.test.tsx`,
  `opro-parameter-tab.test.tsx`.
- **Layout schema:** `opro.json` validates.
- **Integration:** routing test for `/opro` and `/opro/:runId`.
- **Cross-rail:** test that a Trainer run with an OPRO child surfaces
  the cross-link in its Agents tab.

## Out of scope

- The OPRO emit logic (Brief 14).
- Trainer detail page (Brief 13).
- Other optimizers (APE, TGD, Momentum) — see A3 above.

## Hand-off

PR body with:
1. Acceptance-criteria checklist.
2. Screenshots of `/opro` (index), `/opro/:runId` Overview and History.
3. Confirmation that the Trainer-OPRO cross-link works (this requires
   either Brief 13 to be merged first, or a coordinated landing).
