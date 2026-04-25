# examples/

Start here: **`00_hello.py`** — one leaf, one call, ~35 lines. Then work through the numbered examples below, one per pillar of the operad vision.

Each example is self-contained, runs offline by default (`--offline` is a parity flag for `scripts/verify.sh`), and prints a terminal walkthrough you can follow line-by-line. Pass `--live` (where supported) to hit a real `llama-server` configured via `_config.py`.

| # | Script                                  | What it shows |
| - | --------------------------------------- | ------------- |
| 0 | `00_hello.py` ← **start here**         | A single leaf agent, a single `await agent(x)`, and `print(out.response.response)`. The minimal shape of every operad program. |
| 1 | `01_composition_research_analyst.py`    | A single `await agent(x)` over four nested composition layers (Pipeline ⊃ Parallel × 3 ⊃ Pipeline ⊃ ReAct). 28 typed nodes, 27 edges, all checked at `build()` time. |
| 2 | `02_talker_reasoner_intake.py`          | The new `TalkerReasoner` algorithm walking a user through a four-stage scenario tree. Exercises the `stay`/`advance`/`branch`/`finish` decision branches end-to-end. |
| 3 | `03_train_config_temperature.py`        | A small training loop that tunes `config.sampling.temperature` via `EvoGradient` with `SetTemperature` mutations. Score climbs from 0.15 → 1.00 across four generations. |
| 4 | `04_evolutionary_best_of_n.py`          | A complex training loop: subclassed `EvoGradient` whose `step()` (a) refreshes the mutation pool every generation, (b) launches Best-of-N **in parallel** across all individuals, (c) keeps the top-K survivors. |

Run them all from the repo root:

```bash
uv run python examples/00_hello.py
uv run python examples/01_composition_research_analyst.py
uv run python examples/02_talker_reasoner_intake.py
uv run python examples/03_train_config_temperature.py
uv run python examples/04_evolutionary_best_of_n.py
```

Or run the offline surface in one shot via `scripts/verify.sh`.

## Live (LLM-backed) mode

Examples 1 and 2 accept `--live` to talk to a `llama-server`:

```bash
OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \
OPERAD_LLAMACPP_MODEL=qwen2.5-7b-instruct \
  uv run python examples/01_composition_research_analyst.py --live
```

`_config.py` centralises the canonical local target; override with
`OPERAD_LLAMACPP_HOST` / `OPERAD_LLAMACPP_MODEL`.

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
