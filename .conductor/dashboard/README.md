# Dashboard revamp — agent task plan

> Goal: turn `apps/dashboard/` from "not usable" into the canonical lens
> for everything **beyond** what Langfuse already shows: algorithm-internal
> state (populations, debates, sweeps, training drift), cross-run
> experiment analysis, benchmark visualization, cassette determinism.
> Strategic split: *agent traces → Langfuse; everything else → dashboard.*

This folder contains a prioritized plan split into discrete agent tasks
named `<sequential-iter>-<parallel-iter>-<feature>.md`. Agents inside
the same iteration run in parallel; once all their PRs land, the next
iteration's agents launch. This document is the orientation every agent
should read first.

---

## Why this revamp

What I observed running the system on 2026-04-25 (full ideation in
`.context/dashboard_ideation.md`):

1. **The React 19 SPA from PR #127 was never built.**
   `apps/dashboard/operad_dashboard/web/` doesn't exist in source or
   Docker. The wheel's `force-include` points at a directory `make
   build-frontend` never produced. Users see the legacy
   server-rendered HTML fallback in `app.py`.

2. **HTTP-attach loses events.** A 6-generation `EvoGradient` demo
   delivered 1 of 6 generation events to the dashboard. The parent run
   was stuck `state="running"` because `algo_end` was lost on demo
   exit. Charts looked broken.

3. **One demo created 100 runs in the registry.** Every inner candidate
   scoring registered as its own `algorithm_path=null` root run. The
   parent EvoGradient run was buried among 97 sub-runs. No
   parent-child grouping in the runs list.

4. **Tabs are baked in EvoGradient-shaped.** Every run gets the same
   seven tabs. The "evolution" tab is meaningless for non-evolutionary
   algorithms.

5. **Default "all runs (live)" mode in the evolution tab never
   backfills.** Users see blank charts even when full data exists in
   the registry; switching to "selected run" populates correctly.

6. **No cross-run comparison anywhere.** Every analytical question
   that spans runs (did optimizer A beat B? did this rule survive
   across seeds?) is impossible.

---

## Strategic split: Langfuse vs dashboard

After this revamp:

**Langfuse owns**: per-`AgentEvent` spans, prompt/completion text,
token counts, cost, latency, provider errors. The `OtelObserver`
already ships these and aligns `trace_id == run_id` for direct linking.

**Dashboard owns**:
- Algorithm-internal state: populations, mutations, survivor lineage,
  debate rounds, sweep cells, candidate beams, training loss,
  parameter drift (actual *text* diffs, not hashes), gradient flow,
  LR schedules.
- Cross-run experiment views: pin N runs, overlay fitness curves,
  side-by-side prompt diffs, A/B winners.
- Benchmark visualization (TGD vs Momentum vs EvoGradient vs OPRO vs
  APE vs Sweep across tasks).
- Cassette / determinism reports.
- Causal lineage of prompts across runs.

The dashboard should drop its own token/cost tracking in favour of a
"Langfuse summary" card with a deep-link.

---

## Iteration overview

```
Iteration 1 — Foundation (3 parallel agents)
  1-1  Operad → dashboard transport reliability      (operad/dashboard.py)
  1-2  Dashboard backend hardening                   (apps/dashboard/operad_dashboard/)
  1-3  SPA build pipeline + CI                       (Dockerfile, Makefile, CI only)
       → outcome: real demos populate the dashboard cleanly; SPA shipped.

Iteration 2 — Frontend infrastructure (3 parallel agents)
  2-1  Run-list IA & sidebar                         (RunListPage, sidebar, ui store)
  2-2  Renderer + backfill + SSE coherence           (DashboardRenderer, hooks, registry)
  2-3  Pinned-runs primitive                         (NEW store + hook)
       → outcome: every algorithm renders correctly; primitives ready for cross-run.

Iteration 3 — Per-algorithm pages (5 parallel agents)
  3-1  Trainer bespoke page                          (loss + drift-diff + gradient-log)
  3-2  Debate bespoke page                           (round text + critic feedback)
  3-3  Sweep new page                                (parameter heatmap)
  3-4  Iteration-loop layouts                        (Beam upgrade + Verifier + SelfRefine)
  3-5  Langfuse summary card                         (NEW shared panel + per-event link)
       → outcome: each algorithm has a tailored, populated detail view.

Iteration 4 — Composite & polish (4 parallel agents)
  4-1  Cross-run experiments compare                 (NEW page + diff + curve overlay)
  4-2  Benchmark consumer                            (NEW route + ingest + consumer page)
  4-3  Cassette inspector                            (NEW page + replay + determinism)
  4-4  Run persistence (SQLite mirror)               (registry persistence + replay)
       → outcome: dashboard is an experiment platform, not a single-run viewer.
```

Total: 15 agent tasks across 4 iterations.

---

## Conventions every agent must follow

### Scope discipline

Every task file declares **owned files** and **forbidden files**. Stay
inside your scope. Within an iteration, two agents must never edit the
same file unless explicitly noted. If you need to change something
outside your scope, open a separate question — don't reach for it.

### Tests

- Add tests for new behavior. Repo convention: offline tests via `make
  test`; integration tests opt-in via `OPERAD_INTEGRATION=<backend>`.
- Frontend: `make frontend-test` (vitest) and `make frontend-typecheck`.
- Dashboard tests live in `apps/dashboard/tests/`; frontend tests in
  `apps/frontend/src/**/*.test.ts(x)`.

### Style

- Match surrounding code; the repo's CLAUDE.md sets the bar.
- TypeScript strict mode is on. No `any` without a comment.
- Python: type hints, pydantic where it makes sense, async where the
  surrounding code is async.
- No new top-level dependencies without a strong reason; prefer
  what's already in `package.json` / `pyproject.toml`.

### Don't over-build

- Implement what the task asks; resist refactors of unrelated code.
- Don't add error handling for impossible cases. Don't add
  feature-flagging or backwards-compat shims unless the task says so.
- If you discover a problem outside your scope, document it in a
  comment in the PR description — don't fix it.

### Investigate before deciding

The task descriptions hint at direction; you decide implementation.
Search SOTA libraries (e.g. for diffs: `react-diff-viewer-continued`,
`diff`, `unidiff`), look at how the repo solved similar problems
elsewhere, and pick the smallest viable approach.

### Verify

- Don't claim "done" without running the demo path the task affects:
  `uv run --extra observers python apps/demos/agent_evolution/run.py
  --offline --dashboard` for evolutionary; the same with appropriate
  flags for trainer/debate/etc.
- For UI work: open the dashboard with playwright (`mcp__expect__open
  http://localhost:7860/`) and verify visually.
- If the task touches `app.py`, restart `operad-operad-dashboard-1`
  before testing.

### Docker reality

The user runs everything via `docker compose up -d`. Local
`operad-dashboard` processes can race with the container on port 7860.
If a demo posts to localhost and gets routed to the wrong dashboard,
that's a port collision — kill stray local processes before debugging.

---

## Cross-iteration contracts

These are the API surfaces that downstream iterations rely on. If you
need to change them, raise it explicitly so dependent tasks adapt.

| Iteration | Contract exposed                                                                  |
|-----------|-----------------------------------------------------------------------------------|
| 1-1       | New envelope kind `graph_envelope`. AgentEvent metadata gets `parent_run_id`.    |
| 1-2       | `/runs?include=synthetic`, `/runs/{id}/children`, `/api/manifest`. SPA mandatory. |
| 1-3       | Built docker image has `/app/operad_dashboard/web/index.dashboard.html`.          |
| 2-1       | Run-list emits multi-select events; consumes pinned-runs store.                   |
| 2-2       | All `.sse` data sources backfill from `.json` siblings. Layout auto-discovery.    |
| 2-3       | `usePinnedRuns()` hook + `PinIndicator` component.                                |
| 3-5       | `<LangfuseSummaryCard runId={…} />` shared panel.                                 |
| 4-1       | `/experiments?runs=…` route stable.                                               |
| 4-2       | `/benchmarks/_ingest` accepts `examples/benchmark/run.py --out` JSON shape.       |

---

## Reference material in the repo

- `VISION.md` — guiding architecture; algorithms-as-agents thesis.
- `INVENTORY.md` — capability surface.
- `TRAINING.md` — Trainer/optim internals.
- `apps/README.md` — how dashboard/studio relate to operad.
- `apps/dashboard/README.md` — the dashboard package.
- `apps/frontend/README.md` — the SPA.
- `.context/dashboard_ideation.md` — the long-form ideation doc this
  plan was distilled from.

If a task's premise looks wrong, **investigate before building**. The
investigation that produced this plan happened on 2026-04-25; reality
may have moved.
