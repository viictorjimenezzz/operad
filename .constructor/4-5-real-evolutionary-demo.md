# `agent_evolution` demo: ship a real evolutionary loop

## Goal
The demo today is theatre: a seeded agent with `auto_tune()` that uses an optimizer under the hood — no population, no selection pressure, no diversity collapse to watch. The README sells this as the showcase. Replace it with a genuine evolutionary loop driven by `EvoGradient`: population of N variants, fitness, selection, mutation via `RewriteAgent`s, observable diversity collapse, plotted on the dashboard.

## Context
- `apps/demos/agent_evolution/` — current run.py, seed.py, metric.py.
- `operad/optim/evo.py` — `EvoGradient` lives here; population-search logic.
- `apps/dashboard/operad_dashboard/routes/fitness.py` — already consumes `generation` events for fitness curves; `mutations.py` consumes `op_attempt_counts` / `op_success_counts`.

## Scope

**In scope:**
- `apps/demos/agent_evolution/run.py` — replace the current single-agent flow with: build a population of K variants of the seed (e.g. perturbed `rules` lists), score each on the metric, select top-M, mutate via `EvoGradient`, repeat for G generations. Emit `generation` events with `population_scores`, `op_attempt_counts`, `op_success_counts`.
- `apps/demos/agent_evolution/population.py` (new, optional) — small helper for population init/selection if `run.py` would otherwise grow past ~120 lines.
- `apps/demos/agent_evolution/README.md` — update with the new mechanics, expected dashboard panels, expected runtime.
- A test under `tests/apps/demos/` (or `apps/demos/tests/`) that runs the demo with a fake LLM for 2 generations and asserts: events emitted with the right keys, fitness improves, diversity (unique `hash_content` count) tracks down monotonically.

**Out of scope:**
- Modifying `EvoGradient` itself.
- Changing the metric (it's fine).
- Wiring this into `verify.sh` — the existing fast offline path should not be displaced.
- Anything outside `apps/demos/agent_evolution/`.

**Owned by sibling iter-4 tasks — do not modify:**
- `apps/studio/`, `apps/dashboard/`, `Makefile`, `scripts/`, `examples/benchmark/`, `operad/algorithms/sweep.py`, `apps/dashboard/operad_dashboard/routes/sweep.py`, `tests/runtime/test_otel_langfuse.py`.

## Implementation hints
- Population size 6-10 is enough to demo selection + collapse. G=4-6 generations.
- "Diversity collapse" — track unique `hash_content` per generation; assert it decreases. Visualize alongside fitness in the dashboard.
- Keep `--offline` working: a fake LLM whose output is deterministic per (input, prompt-hash) modulo a small mutation knob produces visible improvement without network.
- Include a one-line "what to look for" pointer in the demo README: "open dashboard at :7860; you'll see fitness rise and the mutation heatmap concentrate on `rules`-targeted ops by gen 3."

## Acceptance
- Demo runs offline in under ~30s.
- Dashboard panels populate with genuine data.
- Test pins fitness improvement and diversity decrease.
- README accurately describes what runs.
