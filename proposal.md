# Honest answer first: pure parallel fan-out will hurt this project, and pure serial will be slow. The right shape is a **staged plan with parallelism only where the cleavage planes are clean**, plus a Stage 0 that writes tight per-section briefs so subagents can't drift on creativity-vs-rigor.

Below is the execution plan I'd run if you say go.

---

## **The cleavage planes (where parallelism is and isn't safe)**

Reading the actual file graph:

- **Critical singletons** that almost everything else depends on: `apps/frontend/src/dashboard/routes.tsx`, `apps/frontend/src/components/runtime/dashboard-renderer.tsx`, `apps/frontend/src/lib/hash-color.ts`, the new `RunTable` primitive, and `apps/frontend/src/styles/tokens.css`. Two agents touching any of these in parallel will conflict.
- **Naturally parallel:** per-algorithm JSON layouts and their bespoke components (`talker_reasoner.json`, `sweep.json`, `evogradient.json`, etc.) — each lives in its own folder once the registry pattern is in place. **Backend deltas** in `apps/dashboard/operad_dashboard/routes/` are also nicely separable per route.
- **Sequencing constraint:** the new `RunTable` is consumed by 5+ pages. Layout-resolver wiring is a prerequisite for any per-algorithm tab work to even render.

So the order is forced: **primitives → wiring → fan-out → convergence**.

---

## **The 4-stage plan**

### **Stage 0 — Per-section briefs (me, sync, ~30 min)**

I expand `proposal.md` into a folder of focused briefs:

.context/dashboard-redesign/

  00-CONTRACTS.md           ← shared API/JSON-layout/component-prop contracts

  01-primitives.md          ← RunTable, hashColor palette, MultiSeriesChart fix

  02-wiring.md              ← LayoutResolver routing, AlgorithmDetailLayout

  03-agent-overview.md      ← single-invocation Overview redesign

  04-agent-group.md         ← group page redesign + Train/Metrics rename

  05-algo-sweep.md

  06-algo-beam.md

  07-algo-debate.md

  08-algo-evogradient.md    ← Lineage + Best-individual diff

  09-algo-talker.md         ← Tree + Transcript + Decisions

  10-algo-selfrefine.md

  11-algo-verifier.md

  12-algo-autoresearcher.md

  13-training-rail.md

  14-backend-deltas.md      ← metrics, parameters, payload extensions, OPRO emit

  15-universal-agents-tab.md

Each brief is structured identically (this is the rigor anchor):

## Goal

## Files to touch (with current file:line refs)

## API contract (props / JSON shape / backend route)

## Design alternatives (2-3, with the recommendation flagged)

## Acceptance criteria (what running the dashboard should show)

## Test plan (which existing tests must still pass + what new ones to add)

## Out of scope

The "Design alternatives" section is where creativity is licensed — the subagent must pick one and justify, not invent a fourth. The "Acceptance criteria + Test plan" is where rigor is enforced — done means demonstrably done.

`00-CONTRACTS.md` locks the shared types: `RunTable` props, the new JSON-layout `Tabs` element shape, the `Agents`-tab data fetcher contract, the color-palette tokens, the `metrics` field shape on `OperadOutput.metadata`. Once locked, parallel agents can work without negotiating.

### **Stage 1 — Critical-path primitives (single agent, serial, ~1 day)**

Done by one agent (probably me) because every change here is consumed by everything downstream:

- New `components/ui/run-table.tsx` primitive (with column-toggle, sort, sparkline column, multi-select).
- `lib/hash-color.ts` rounds into the 12-hue qualitative palette.
- `tokens.css` adds `--qual-1..12`.
- Fix `useRunSeries` and `useScatter` to flatten to a single multi-point series (the "colored line" bug).
- Drop `InvocationsBanner` from the single-invocation Overview path; kill the "Latest invocation" eyebrow.
- `AgentFlowGraph`: single-node empty-state fix (render the leaf card instead of "graph unavailable").

Smoke test: existing pages still render, MultiSeriesChart produces visible lines, sidebar dots visibly match table swatches.

### **Stage 2 — Backbone wiring (single agent, serial, ~1 day)**

Also done by one agent because it touches the route table:

- Replace `runDetailChildren` for `/algorithms/:runId`, `/training/:runId`, `/agents/:hash/runs/:runId` with three different layout components (`AlgorithmDetailLayout`, `TrainingDetailLayout`, `AgentRunDetailLayout`).
- `AlgorithmDetailLayout` calls `resolveLayout(summary.algorithm_path)` and feeds it to `DashboardRenderer`.
- Add the **universal** `Agents` **tab** to all per-algorithm JSON layouts in one PR (so Stage 3 doesn't have to coordinate). The tab is a single new component that fetches `/runs/:id/children` and renders a `RunTable`.
- Add the **universal** `Events` **tab** as one component too.

Smoke test: every algorithm's detail page resolves to *its own* JSON layout and renders the tab strip declared there. The orphaned layouts come back to life.

### **Stage 3 — Parallel fan-out (4–5 subagents in worktrees, ~2-3 days each)**

This is where parallelism pays off. Each subagent operates in its **own git worktree** (via `best-of-n-runner` or just `git worktree add`), works on a disjoint file set, and merges back at the end. Suggested split:


| **Subagent**            | **Scope**                                                                                                                                    | **Worktree branch**     |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| **A — Agents-rail**     | Single-invocation Overview redesign (brief 03), Group page redesign (brief 04), Train tab, Metrics tab                                       | `wandb/agents-rail`     |
| **B — Algos-quant**     | Sweep (heatmap + cells + parallel-coords) + Beam (leaderboard) + Verifier (briefs 05, 06, 11)                                                | `wandb/algos-quant`     |
| **C — Algos-narrative** | Debate (rounds + transcript) + SelfRefine (refine→reflect ladder) + AutoResearcher (Plan + Attempts swimlane) (briefs 07, 10, 12)            | `wandb/algos-narrative` |
| **D — Algos-creative**  | TalkerReasoner Tree + EvoGradient Lineage + Best-individual diff (briefs 08, 09) — the highest-creativity briefs                             | `wandb/algos-creative`  |
| **E — Backend**         | All backend deltas (brief 14) — metrics endpoint, parameters endpoint, algo_start payload extensions, OPRO emit, `metrics: dict` propagation | `wandb/backend-deltas`  |


This split is chosen so:

- **No two subagents touch the same file.** Each gets a different per-algorithm layout JSON + its own component folder.
- **Subagent E (backend) can run start-to-finish in parallel** with everyone else — `00-CONTRACTS.md` is the bridge.
- **D gets the longest leash** (most creative) and the shortest scope; A gets the most file churn and the least novelty.
- **The Training rail is intentionally not in Stage 3** — see Stage 4.

Each brief mandates: the subagent reads the brief in full, writes a 5-bullet implementation outline back to me before starting, and ends with `uv run pytest tests/` + `make build-frontend` green.

I would **not** use `best-of-n-runner` here — that subagent type is for "best of N parallel attempts at the same task". The work above is genuinely different per agent, so plain `generalPurpose` subagents in worktrees are the right call.

### **Stage 4 — Convergence + Training rail (single agent, ~1-2 days)**

Done by one agent (me) after Stage 3 worktrees merge:

- Resolve conflicts (mostly the registry index files).
- Wire the now-rich JSON layouts into a polished default presentation per rail.
- Build the Training rail's compare mode and PromptTraceback tab (brief 13) — left for last because it depends on backend deltas (Stage 3 subagent E) being live.
- Polish: keyboard shortcuts, breadcrumb consistency, color audit, density audit.
- Run all tests, fix what broke, manual QA against examples 01–04 and a fresh sweep.