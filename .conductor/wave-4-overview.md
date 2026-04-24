# Wave 4 — overview

This document is the index for Wave 4 briefs. It captures:

1. The **library-vs-apps split** (what lives inside `operad/` vs what
   lives in `apps/`).
2. The full **feature brainstorm** partitioned into those two buckets
   and into "Wave 4 scope" vs "deferred".
3. The **dependency DAG** for the briefs in `.conductor/4-*.md`,
   `.conductor/5-*.md`, and `.conductor/6-*.md`.

For the audit and open-issue groups, see [`../ISSUES.md`](../ISSUES.md).
For the broader Wave-4 rationale, see the plan the user approved:
`~/.claude/plans/system-instruction-you-are-working-vectorized-eclipse.md`.

---

## 1. Library-vs-apps split

`operad` is the `torch.nn` of local-first agent systems (VISION.md §1).
Anything that lives *inside* `operad/` needs to satisfy three tests:

1. **It's a primitive or an extension of one.** Typed contracts,
   composition, tracing, observers, metrics, algorithms, launchers.
2. **It's reusable across applications.** Multiple downstream apps
   could consume it without modification.
3. **It does not drag in heavyweight UI/server dependencies.** Rich
   is optional already; adding a mandatory FastAPI/Jinja2 surface
   would blow up the install footprint.

Anything that fails one of these tests is an **application that uses
operad**, not a library primitive. Apps live at the repo root under
`apps/<name>/`, each with its own `pyproject.toml`-style optional extra
(`operad[dashboard]`, `operad[playground]`, etc.) or as standalone
subprojects.

The analogy: PyTorch ships `torch.nn`; TensorBoard ships separately.
`operad` ships the event schema, the observer protocol, and the
registry; `apps/dashboard/` ships the web UI that subscribes to them.

### What goes inside `operad/`

| Feature | Where it slots in |
|---|---|
| Algorithm event schema + emission (H-1, A-1) | `operad/runtime/events.py`, `operad/algorithms/*.py`, `operad/runtime/observers/base.py` |
| `SlotRegistry.occupancy()` + `SlotOccupancy` (M-1) | `operad/runtime/slots.py` |
| `CostObserver` wired to registry (N-1) | `operad/runtime/cost.py` |
| Sentinel proxy for composite payload-branching (H-6) | `operad/core/build.py`, `operad/utils/errors.py` |
| `Evolutionary` clone-before-mutate + `Op.undo()` (H-2) | `operad/algorithms/evolutionary.py`, `operad/utils/ops.py` |
| `FakeRetriever` / `BM25Retriever` (A-4) | `operad/agents/reasoning/components/` |
| `Agent.auto_tune(dataset, metric)` one-liner (A-3) | `operad/core/agent.py`, `operad/utils/ops.py` |
| Config hygiene: warn on dead knobs, validate `Entry`, audit `Switch` (M-2, M-4, M-6) | `operad/core/config.py`, `operad/benchmark/entry.py`, `operad/agents/reasoning/switch.py` |
| Future: sub-agent streaming propagation | `operad/core/agent.py` |
| Future: `operad.infer_schema(examples=[...])` | `operad/core/` |
| Future: cost-aware `Router(by=Budget, ...)` | `operad/agents/reasoning/components/router.py` |

### What goes inside `apps/` (NEW top-level folder)

| Feature | Folder |
|---|---|
| Web dashboard (FastAPI + SSE + htmx + Mermaid.js) (A-2) | `apps/dashboard/` |
| Showcase demos (flagship `agent_evolution`, stretch `research_arena`) | `apps/demos/` |
| Future: static HTML report generator | `apps/report/` |
| Future: drag-drop playground for building agents | `apps/playground/` |
| Future: `operad-mcp serve` — exposes an agent as an MCP tool | `apps/mcp-server/` |
| Future: benchmark leaderboard (run one agent across backends) | `apps/leaderboard/` |
| Future: time-travel REPL debugger over traces | `apps/debugger/` |

Each app's `README.md` explains how to install it, how to run it, and
which operad primitives it depends on. Apps can have their own tests.
Apps import from `operad` like any other downstream user — they do
**not** modify `operad/` internals.

### The existing `examples/` folder

`examples/` is for small, educational mini-tutorials (one per
abstraction). It stays where it is. `apps/demos/` is for *narrative*
end-to-end stories that combine multiple features, often with a
dashboard or Rich UI. Examples teach, demos showcase.

---

## 2. Feature brainstorm — bucketed

### Library primitives (inside `operad/`) — all Wave 4 scope unless noted

- Algorithm event emission (H-1, A-1) — iteration 4
- Slot occupancy public API (M-1) — iteration 4
- CostObserver wiring (N-1) — iteration 4
- Evolutionary rollback (H-2) — iteration 4
- Sentinel proxy (H-6) — iteration 4, **time-boxed 1 week**
- Config hygiene bundle (M-2, M-4, M-6) — iteration 4
- Retriever starter pack (A-4) — iteration 4
- `agent.auto_tune()` one-liner (A-3) — iteration 5
- **Wave 5+**: sub-agent streaming propagation, `operad.infer_schema`,
  cost-aware routing, typed `Router(by=Enum)` ergonomics, async
  `Metric.score_batch` as a protocol not a default.

### Apps (inside `apps/`) — selective Wave 4 scope

- Web dashboard (A-2) — iteration 5
- `apps/demos/agent_evolution/` flagship — iteration 6
- **Wave 5+**: static HTML report (rolls into dashboard replay first),
  drag-drop playground, MCP server, benchmark leaderboard, time-travel
  REPL debugger.

### Explicitly deferred

- Agent marketplace / registry — not soon.
- Interactive web agent builder — Wave 5+, UX-heavy.
- Hosted multi-tenant dashboard — out of scope for a local-first
  library.

---

## 3. Dependency DAG

```
Iteration 4 (all parallel, operad/ only):

  4-1 algorithm events ─┐
  4-2 slot occupancy ────┼──▶ 5-2 dashboard app (apps/dashboard/)
  4-3 cost observer ────┘       │
                                │
  4-4 evolutionary rollback ──▶ 5-1 auto_tune (operad/)
                                │
  4-5 sentinel proxy            │
                                ▼
  4-6 config hygiene       6-1 demos showcase (apps/demos/)
                                ▲
  4-7 retrievers ───────────────┘ (agent_evolution uses auto_tune;
                                   research_arena uses retrievers)

Iteration 5 (parallel, depends on 4-*):
  5-1 auto_tune one-liner       (operad/)
  5-2 dashboard app             (apps/dashboard/)

Iteration 6 (depends on 5-*):
  6-1 agent_evolution demo      (apps/demos/)
```

Briefs 4-1 through 4-7 are strictly independent: none reads from a file
another writes, so seven agents can run concurrently. The only shared
surface is `operad/runtime/observers/base.py` (widened by 4-1 only);
4-3's `CostObserver` imports the new union but does not edit `base.py`.

5-1 depends on 4-4 for safe mutation; 5-2 depends on 4-1 + 4-2 + 4-3
for the data it renders.

6-1 imports `auto_tune` (5-1) and launches the dashboard (5-2).

---

## 4. Contributor checklist (recap)

Every brief inherits VISION §9's rules:

1. Preserve the components-vs-algorithms split.
2. Declare component contracts as class attributes.
3. Keep composite `forward` as a router, not a calculator.
4. Keep `__init__` free of side effects.
5. Add offline tests; prefer `FakeLeaf`-style helpers over cassettes.
6. Extend, don't fork, the public API under `operad/core/` and
   `operad/utils/errors.py`.

Plus:

7. **Library-vs-apps discipline.** If a brief's target lives in
   `apps/`, do not modify `operad/` internals beyond what the brief
   explicitly authorises. If a brief's target lives in `operad/`, do
   not introduce a FastAPI/uvicorn/JS build dependency.
