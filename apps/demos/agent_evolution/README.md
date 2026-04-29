# agent_evolution — the flagship operad demo

A seed agent is evolved over several generations using an explicit
`EvoGradient` population loop. Each generation:

1. **Mutate** — clone every individual and apply a random mutation (e.g.
   `AppendRule`, `TweakRole`).
2. **Score** — evaluate each individual on the offline dataset.
3. **Select** — keep the top half; discard the rest.
4. **Refill** — mutate survivors to restore population size.

The fitness curve climbs as the metric rewards accumulated rule, role,
task, and temperature changes. Diversity (unique `hash_content` values in
the population) collapses as the gene pool converges. Both are printed each
generation and written to a JSONL trace.

The whole thing runs offline — the seed's output is a deterministic function
of its mutation state, so no model server is required.

## Run it

```bash
uv run python apps/demos/agent_evolution/run.py --offline
```

Flags:

- `--generations N` (default 7) — how many rounds of mutate/score/select.
- `--population M` (default 10) — individuals per generation.
- `--seed N` (default 0) — deterministic RNG. Same seed → same result.
- `--dashboard [HOST:PORT]` — attach to a running `operad-dashboard`
  server (default `127.0.0.1:7860`). If no server is reachable the
  demo prints a one-line hint and continues.

Expected runtime: ~10 s offline.

The fitness trace is written to `/tmp/agent-evolution-trace.jsonl` (one
JSONL row per generation, with `gen`, `best`, `mean`, `population_scores`,
and `diversity`).

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
(pass `--no-open` to skip). Open the **Evolution** tab — you'll see the
fitness curve rise and the mutation heatmap concentrate on
`rules`-targeted ops by generation 3.

## What to look for

- **Fitness curve** rises as the best lineage accumulates rule, role, task,
  and config changes toward the target score.
- **Mutation heatmap** (mutations tab): by gen 3 the successful ops are
  concentrated around useful prompt/config edits — that's selection pressure at work.
- **Diversity** (printed each generation): starts at the population size,
  then collapses to 1–2 unique variants once the top genotype dominates.

## Reproduce

```bash
uv run python apps/demos/agent_evolution/run.py \
    --offline --generations 2 --population 4 --seed 0
```

Completes in <5 s. Two runs with identical flags produce identical output.
