# agent_evolution — the flagship operad demo

A seed agent evolved over a handful of generations via
`Agent.auto_tune`. Each generation the population is mutated, scored,
and culled; the fitness curve climbs monotonically. The whole thing
runs offline — the seed's output is a deterministic function of its
rule count, so no model server is required.

## Run it

```bash
uv run python apps/demos/agent_evolution/run.py --offline
```

Flags:

- `--generations N` (default 4) — how many rounds of mutate/score/cull.
- `--population M` (default 6) — individuals per generation.
- `--seed N` (default 0) — deterministic RNG. Same seed → same result.
- `--dashboard [HOST:PORT]` — attach to a running `operad-dashboard`
  server (default `127.0.0.1:7860`). If no server is reachable the
  demo prints a one-line hint and continues.

The fitness curve is written to `/tmp/agent-evolution-trace.jsonl`
(one row per generation, with `best`, `mean`, and full
`population_scores`).

## Watch it live

In one terminal:

```bash
uv run operad-dashboard --port 7860
```

In another:

```bash
uv run python apps/demos/agent_evolution/run.py --offline --dashboard
```

The demo opens http://127.0.0.1:7860 in your browser automatically
(pass `--no-open` to skip). Algorithm events stream in as each
generation completes; the **Evolution** tab shows the fitness curve
and population scatter building up generation-by-generation, and the
**Graph** tab renders the Mermaid graph of the seed agent.

## What this demonstrates

`Agent.auto_tune(dataset, metric)` is the one-liner that turns
"agents optimize agents" from a slogan into a function call. Under
the hood it wraps `operad.algorithms.Evolutionary` with a sensible
default mutation set; the seed is never mutated in place, and each
generation's best individual is preserved via the Phase 0 rollback
work.

## Reproduce

```bash
uv run python apps/demos/agent_evolution/run.py \
    --offline --generations 2 --population 4 --seed 0
```

Completes in <10s. Two runs with identical flags produce identical
output.
