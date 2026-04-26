# examples/

Four end-to-end examples — one per pillar of the operad vision. Every
example talks to a **real** LLM via the backend declared in `_config.py`
(defaults: `127.0.0.1:9000`, `google/gemma-4-e2b`; override with
`OPERAD_LLAMACPP_HOST` / `OPERAD_LLAMACPP_MODEL`). No fakes, no
deterministic stand-ins — these are full live runs.

Each example accepts `--offline` as a verify.sh-friendly no-op (prints a
banner and exits 0); without that flag they probe reachability and
exit cleanly with an error if the backend is not up.

| # | Script                                  | What it shows |
| - | --------------------------------------- | ------------- |
| 1 | `01_agent.py`    | A single `await agent(x)` over four nested composition layers (Sequential ⊃ Parallel × 3 ⊃ Sequential ⊃ ReAct). 28 typed nodes, 27 edges, all checked at `build()` time. Every leaf is a vanilla `Planner(...)` / `Reasoner(...)` / `ReAct(...)` instance — no subclasses. |
| 2 | `02_algorithm.py`          | `TalkerReasoner` over a four-stage scenario tree with two run paths: interactive REPL (`input()`) by default, or `--scripted` replay. Exercises stay/advance/branch/finish decisions. |
| 3 | `03_training.py`        | Training loop with `MutationBeam`: ReAct-in-Parallel mutation proposal branches, typed `set_temperature` proposals, and Beam+judge selection. A reference-free length-band metric (no second LLM call) tracks progress. |
| 4 | `04_evolutionary.py`          | Evolutionary loop with `MutationBeam` over prompt-rule mutations (`append_rule`, `replace_rule`, `drop_rule`) and Beam+judge top-k survivor selection across generations. Real `Reasoner` agent + reference-free length-band metric. |

Run them from the repo root:

```bash
uv run python examples/01_agent.py
uv run python examples/02_algorithm.py
uv run python examples/03_training.py
uv run python examples/04_evolutionary.py
```

To stream runs into `operad-dashboard` from a separate process:

```bash
# terminal A
uv run operad-dashboard --port 7860

# terminal B
uv run python examples/01_agent.py --dashboard
```

To also export spans to self-hosted Langfuse, set OTel env once and run
with `OPERAD_OTEL=1`:

```bash
OPERAD_OTEL=1 \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:3000/api/public/otel \
uv run --extra otel python examples/01_agent.py --dashboard
```

All four scripts (`01`..`04`) accept `--dashboard [HOST:PORT]` and
`--no-open`.

`scripts/verify.sh` runs each one with `--offline` (the no-op path) so
CI stays green without a model server. To exercise the live paths,
start a llama-server pointed at the model in `_config.py` and run them
without `--offline`.

## YAML / CLI configuration

`config-react.yaml` + `task.json` are kept for the CLI walkthrough in
the top-level [`README.md`](../README.md):

```bash
uv run operad run   examples/config-react.yaml --input examples/task.json
uv run operad trace examples/config-react.yaml
uv run operad graph examples/config-react.yaml --format json
```

See [`operad/configs/README.md`](../operad/configs/README.md) for the
full schema.
