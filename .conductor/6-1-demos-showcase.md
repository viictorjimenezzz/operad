# 6 · 1 — Showcase demos — `apps/demos/`

**Addresses.** The curated "look what operad can do" story the
library is missing today. `demo.py` at the repo root is a framework
introspection tour (prompts → graph → invoke → trace → mutation
diff). It is not a *task* showcase. The existing `examples/` files
are mini-tutorials, not narrative demos. See
[`../ISSUES.md`](../ISSUES.md) Group J.

**Depends on.**
- 5-1 (`agent.auto_tune()` one-liner) — the `agent_evolution` demo
  uses it.
- 5-2 (dashboard app) — both demos launch the dashboard for live
  observation.
- 4-1 (algorithm events) — dashboard needs these to render.
- 4-7 (retrievers) — the stretch `research_arena` demo uses
  `FakeRetriever`.

**Blocks.** Nothing. This is the payoff brief.

---

## Required reading

- `.conductor/wave-4-overview.md` §1 — library-vs-apps split. Demos
  live in `apps/demos/`, NOT inside `operad/`.
- `demo.py` at the repo root — the existing framework tour. Keep it.
  This brief is additive.
- `examples/` — the mini-tutorials. Keep them. Demos complement them.
- `examples/_config.py` — reuse `local_config()` and
  `server_reachable()` so demos match existing env-var conventions.
- `operad/algorithms/evolutionary.py` (post-4-4).
- `operad/core/agent.py` post-5-1 (`auto_tune`).
- `apps/dashboard/` (brief 5-2) — how to launch the dashboard.

---

## Goal

Ship one deep flagship demo and a stretch second, both as narrative
end-to-end runs. Each demo has a CLI entry point, an offline fallback,
an optional `--dashboard` flag, and a README with an asciinema/GIF
link.

### Flagship: `agent_evolution`

A deterministic-offline-friendly showcase of
"agents-optimizing-agents": a seed agent is evolved over N generations
using `auto_tune`; fitness improves monotonically; the dashboard (if
launched) shows the fitness curve live.

### Stretch: `research_arena`

AutoResearcher with a `FakeRetriever` corpus answering a research
question; the dashboard shows plan → retrieve → reason → verify →
reflect. Ship only if Wave 4 time permits.

## Scope

### New folder layout

```
apps/demos/
  README.md            # narrative index + asciinema link
  _config.py           # shared: import from examples/_config.py or duplicate
  agent_evolution/
    README.md          # story + screenshots + GIF embed
    run.py             # CLI entry
    notebook.ipynb     # same flow, narrated
    metric.py          # the deterministic offline metric
    seed.py            # builds the seed agent
  research_arena/      # stretch
    README.md
    run.py
    corpus.py          # hardcoded Document list
```

### `agent_evolution/run.py`

CLI flags:

- `--offline` (default on if no server reachable) — uses `FakeLeaf`
  seeds whose score is a deterministic function of the number of
  rules. Guarantees a monotonically improving fitness across
  generations.
- `--dashboard [URL]` — starts the dashboard (if URL is empty) or
  attaches to an existing one. Registers `WebDashboardObserver`.
- `--generations N`, `--population M` — tuneables.
- `--seed N` — deterministic RNG.

The script builds the seed, calls
`await seed.auto_tune(dataset, metric, generations=N, population_size=M)`,
prints a before/after diff, and saves a trace to `/tmp/agent-evolution-trace.jsonl`.

Key illustrative code:

```python
async def main(args):
    seed = build_seed()  # composite with a couple of leaves
    await seed.abuild()

    dataset = build_offline_dataset()
    metric = RuleCountMetric()

    improved = await seed.auto_tune(
        dataset, metric,
        generations=args.generations,
        population_size=args.population,
    )

    print("--- before ---")
    rich.print(seed)
    print("--- after ---")
    rich.print(improved)
    print(seed.diff(improved))
```

### `agent_evolution/notebook.ipynb`

The same flow as `run.py` but step-by-step with Rich printouts and
explanatory markdown between cells. Showcases the library interactively
on GitHub.

### `agent_evolution/README.md`

- One-paragraph story: why agents-optimizing-agents matters.
- Screenshots of the dashboard showing the fitness curve.
- Asciinema embed (link only; do not commit binary into repo). Record
  with `asciinema rec` locally.
- Command to reproduce: `uv run python apps/demos/agent_evolution/run.py
  --offline --dashboard`.
- Pointer to the flagship `auto_tune` one-liner.

### `research_arena/` (stretch)

- Wire `AutoResearcher` with `FakeRetriever` (from brief 4-7) over a
  small hardcoded corpus (~8 Document entries about a topic).
- `--offline` replaces the reasoner/critic with `FakeLeaf`s that
  deterministically produce plausible outputs given the retrieved
  documents.
- Dashboard shows each iteration of the reflect loop.

If Wave 4 timeline is tight, ship `agent_evolution` only. Document
`research_arena` as "planned" in the README.

### Root README.md update

In the main `README.md`, add a "Play the demo" section just below the
`## Install` block:

```
## Play the demo

One command, no model server required:

    uv run python apps/demos/agent_evolution/run.py --offline

Add `--dashboard` and open http://localhost:7860 to watch the fitness
curve climb.

[asciinema cast](https://asciinema.org/a/... )
```

Put the asciinema link at repo root too (manual commit after
recording).

### `scripts/verify.sh` update

Add a line that runs `uv run python apps/demos/agent_evolution/run.py
--offline` with a short deterministic budget:

```bash
uv run python apps/demos/agent_evolution/run.py --offline --generations 2 --population 4 --seed 0
```

Guarantees the flagship demo stays green in CI.

---

## Verification

- `uv run python apps/demos/agent_evolution/run.py --offline` completes
  in under 10 seconds and prints a non-trivial improvement diff.
- The script is deterministic given `--seed 0`: two runs produce the
  same final agent hash_content.
- `uv run python apps/demos/agent_evolution/run.py --offline
  --dashboard` launches the dashboard and shows the expected panels.
- `scripts/verify.sh` green (post addition above).
- `notebook.ipynb` runs to completion in Jupyter with no error
  output.

---

## Out of scope

- Recording the asciinema cast. That's a one-off manual step by the
  maintainer after merge.
- `parallel_debate` demo (originally in the plan). Cut for Wave 4.
- A generic `operad demo <name>` discovery CLI. Users run `python
  apps/demos/<name>/run.py` directly; that's discoverable enough.

---

## Design notes — library-vs-apps discipline

- `apps/demos/` is code that *uses* operad, not part of the library.
  It must NOT modify anything under `operad/`.
- If a demo needs a new `Op` or a new helper, add it to operad in a
  separate brief first (it belongs in the library, not in the demo).
- Keep demos focused on one story. `agent_evolution` is the
  flagship; don't stuff five features into it.
- Demos import from `operad.*` like any downstream user. Use
  `from operad import ...` as the canonical form.
- Offline mode is a first-class citizen. Tests must run offline.
- The `examples/` folder stays as-is for mini-tutorials.
  `apps/demos/` is for narrative showcases.
