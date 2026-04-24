# ISSUES — Known risks, footguns, and gaps

Catalogue of problems identified in the codebase. Each issue carries a
severity tag and, once a brief exists, a pointer to the `.conductor/`
file that resolves it. Open issues are grouped by "can land as
independent PRs in the same wave" — each group maps to one brief and
can be taken by a separate agent.

**Severity.**
- **High** — silent correctness risk; user sees wrong behaviour without warning.
- **Med** — honest failure modes but rough DX, dead knobs, or inconsistencies.
- **Low** — polish, docs, or test coverage.

---

## Status log

- **2026-04-23** — all Wave 3 issues closed.
- **2026-04-24** — three pre-existing issues surfaced during Wave 3 PR C
  (F-1/F-2/F-3). F-1 and F-3 were fixed inside that PR; F-2 was deferred.
- **2026-04-24 (Wave 4, Phase 0)** — correctness foundations PR landed:
  - **F-2 (Med) — RESOLVED.** `strands.Agent.__init__` sets
    `self.state = AgentState(...)` on every default-forward leaf, which
    was shadowing operad's `Agent.state()` method and breaking
    `.state()`, `.hash_content`, and `.diff()` on any built leaf (the
    original diagnosis mistook the shadow for a `_children`-to-class
    rewrite — children are untouched). `_init_strands` now relocates
    strands' state to `_strands_state`. `demo.py` stage 5 no longer
    needs its fresh-unbuilt-copy workaround.
  - **H-4 (High) — RESOLVED.** `evaluate()` had no per-row error
    capture; one bad row crashed the whole gather. Now uses
    `return_exceptions=True` and surfaces failures via
    `EvalReport.row_errors` + per-row `error` dict.
  - **H-5 (High) — RESOLVED.** Stream queue was unbounded and silently
    dropped driver exceptions that escaped the driver's own `except`.
    Queue is now bounded (backpressure) and `task.exception()` is
    checked as a safety net.
  - **H-7 (High) — RESOLVED.** `OperadOutput.backend` and
    `OperadOutput.model` are now populated by `_build_envelope`.
    `operad/metrics/cost.py` is a thin re-export shim; canonical
    implementation lives in `operad/runtime/cost.py`. Cost lookups use
    the real `backend:model` key (no more `"unknown:unknown"`).
  - **M-3 (Med) — RESOLVED.** `MetricBase.score_batch` default is
    `asyncio.gather(...)`; async scorers overlap automatically.
  - **M-5 (Low) — RESOLVED.** `operad/py.typed` marker added and
    verified in the built wheel.
- **F-1 (Med)** and **F-3 (Low)** were closed during Wave 3 PR C.

---

## Open issue groups — Wave 4

Each group is self-contained enough that one agent can pick it up
without waiting on another in the same iteration. Groups A–F in
iteration 4 can land in parallel; iteration 5 (G, H) depends on
iteration 4; iteration 6 (showcase demo) depends on 5.

### Iteration 4 — parallel, independent

#### Group A · Algorithm event schema + emission → `.conductor/4-1-algorithm-events.md`
- **H-1 (High).** `operad/algorithms/*.py` never call `registry.notify`.
  BestOfN generating 10 candidates, Evolutionary running 4 generations
  of 8 individuals, AutoResearcher looping plan→read→verify — none of
  it is visible to dashboards. Observers only see leaf invocations.
- **A-1 (Arch).** There is no typed event schema for algorithm-level
  boundaries (`GenerationEvent`, `RoundEvent`, `CellEvent`,
  `CandidateEvent`, `IterationEvent`). Widening the observer protocol
  to carry these is the precondition for the Wave 4 dashboard.

#### Group B · Slot occupancy public API → `.conductor/4-2-slot-occupancy.md`
- **M-1 (Med).** `SlotRegistry` has `SlidingCounter.current(now)` for
  internal use but no public method to query per-endpoint concurrency,
  RPM, and TPM. Any live telemetry layer (dashboard, CLI, alerting)
  has to reach into private state.

#### Group C · CostObserver wiring → `.conductor/4-3-cost-observer.md`
- **N-1 (Arch).** `CostTracker` has an `on_event` method but is never
  registered on the observer `registry`. Dashboards and CLI reports
  can't aggregate cost across runs without a user doing it manually.
  Phase 0 populated `OperadOutput.backend`/`model` so this is now
  a simple wiring task.

#### Group D · Evolutionary rollback → `.conductor/4-4-evolutionary-rollback.md`
- **H-2 (High).** `Evolutionary._mutate` applies an `Op` in place and
  returns the same agent. If a downstream build fails (type error,
  sentinel trap), the agent is left half-modified with no rollback.
  `Op` has no `undo()` hook.

#### Group E · Sentinel proxy → `.conductor/4-5-sentinel-proxy.md`
- **H-6 (High).** VISION §7 iteration 4 commitment. Composite
  `forward()` can branch on payload values today; Pydantic field
  defaults land in the sentinel and the wrong branch traces silently.
  Build-time proxy is needed to turn this into a `BuildError`.

#### Group F · Config hygiene → `.conductor/4-6-config-hygiene.md`
Three unrelated medium-severity items, bundled because each is small
and they share no surface with other groups:
- **M-2 (Med).** `Sampling.reasoning_tokens` is accepted by every
  backend config but silently ignored by most. No warning.
- **M-4 (Low).** `Dataset` coerces raw tuples to `Entry` with no
  runtime schema validation; a row with wrong keys surfaces only at
  metric time.
- **M-6 (Med).** `Switch` tracer invokes every branch during build.
  Branches with side effects (real network calls, file writes) run
  silently during symbolic tracing.

#### Group G · Retriever starter pack → `.conductor/4-7-retrievers.md`
- **A-4 (Arch).** `AutoResearcher` takes a `retriever` param but there
  is no reference implementation. Users have to wire their own search
  backend before the algorithm is usable. Need a `FakeRetriever`
  (static corpus, offline-safe) and a small `BM25Retriever` that
  demos the proper shape.

### Iteration 5 — depends on iteration 4

#### Group H · `agent.auto_tune()` one-liner → `.conductor/5-1-auto-tune.md`
- **A-3 (Arch).** The north-star "agents optimize agents" is
  technically reachable by constructing `Evolutionary(...)` by hand,
  but undiscoverable. A single `Agent.auto_tune(dataset, metric)`
  method makes the story inspectable via `help(agent)`.
  Depends on Group D (Evolutionary rollback) for safe mutation.

#### Group I · Web dashboard (app) → `.conductor/5-2-dashboard-app.md`
- **A-2 (Arch).** `RichDashboardObserver` is terminal-only with no
  metrics, graph, or slot view. No shareable URL, no multi-run
  history. VISION §7 names a live dashboard as an iteration-4 goal.
  **Note.** The dashboard lives in `apps/dashboard/` (not inside
  `operad/`) — it is an application that *uses* operad, not a library
  primitive. Groups A, B, C provide the event stream it consumes.

### Iteration 6 — depends on iteration 5

#### Group J · Showcase demos (app) → `.conductor/6-1-demos-showcase.md`
One flagship `agent_evolution` demo that combines `auto_tune` (H) with
the dashboard (I). Lives in `apps/demos/` — same library-vs-apps
split as Group I.

---

## How to use this file

- When you open a PR, cite the group letter(s) and brief file(s) you
  address in the description.
- If you find a new issue while working, add it here under the
  matching iteration's group (or open a new group entry + brief if it
  warrants one) and include the update in your PR.
- If a fix is out of scope for your brief, drop a one-line note in
  `.conductor/notes/` (create the folder if needed) and keep moving.
- When every group in the current iteration is merged, mark each
  entry "RESOLVED" with a commit hash and move the section to the
  Status log.
