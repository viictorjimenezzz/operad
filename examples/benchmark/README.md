# operad Benchmark

Reliable demo benchmark for operad's benchmark and optimization stack.
It compares frozen baselines, prompt sweep, and optimizer-backed
methods across three synthetic tasks with no external downloads.

## Tasks

| Key  | Name           | Primary metric          | Rows | Description                            |
|------|----------------|-------------------------|------|----------------------------------------|
| cls  | classification | exact_match             | 100  | Banking intent classification          |
| sum  | summarization  | rouge1                  | 50   | One-sentence document summarization    |
| tool | tool_use       | tool_name_exact_match   | 50   | Tool-call selection across five tools  |

`--max-examples N` caps total rows per task before the 80/20 train/test
split is made.

## Methods

| Method    | Offline | Description                                      |
|-----------|---------|--------------------------------------------------|
| no_train  | yes     | Frozen seed agent                                |
| hand_edit | yes     | Manually improved prompt                         |
| sweep     | yes     | Dataset-level grid search over prompt/config     |
| evo       | yes     | `Agent.auto_tune(kind="evo")`                    |
| tgd       | no      | `Agent.auto_tune(kind="textgrad")`               |
| momentum  | no      | `Agent.auto_tune(kind="momentum")`               |
| opro      | no      | `Agent.auto_tune(kind="opro")`                   |
| ape       | no      | `Agent.auto_tune(kind="ape")`                    |

Offline mode defaults to `no_train,hand_edit,sweep,evo`. Live mode
defaults to all methods. Asking for a live-only method with `--offline`
fails before any cell runs.

## Run

```bash
# Offline smoke: no provider, CI-friendly
uv run python -m examples.benchmark.run \
    --offline --max-examples 5 --seeds 0

# Full live run: all tasks, all methods, seeds 0/1/2
uv run python -m examples.benchmark.run --out report.json

# Specific subset
uv run python -m examples.benchmark.run \
    --tasks cls,sum \
    --methods no_train,tgd,evo \
    --seeds 0,1 \
    --train-epochs 3 \
    --out my_report.json
```

Set a provider before running live methods:

```bash
export OPERAD_BACKEND=anthropic
export OPERAD_MODEL=claude-haiku-4-5-20251001
export OPERAD_API_KEY=sk-...
```

To ingest into a running dashboard:

```bash
uv run python -m examples.benchmark.run \
    --offline --max-examples 5 --seeds 0 \
    --dashboard http://127.0.0.1:7860
```

## Report Shape

The runner writes a dashboard-compatible `BenchmarkReport`:

- `cells`: one row per `(task, method, seed)`.
- `summary`: mean/std/token/latency aggregates per `(task, method)`.
- `headline_findings`: short best-method notes per task.
- `metadata`: includes a report name used by dashboard ingest.

Token cost is the total observed prompt + completion tokens from
observer end envelopes during the cell, including training, selection,
and test evaluation. Missing token fields count as zero.
