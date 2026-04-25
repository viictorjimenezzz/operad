# operad

**Agentic workflows you can build, compose, observe, and improve.**

`operad` is an agentic framework on top of
[strands-agents](https://strandsagents.com/). It adds typed
compositional definition, prompt parametrization, and an algorithm
layer where coordinated agents improve other agents — so you can
**train your agentic workflow at the prompt level**, not just write
it.

For the design rationale see [VISION.md](VISION.md). For the
exhaustive capability inventory see [INVENTORY.md](INVENTORY.md). For
training internals see [TRAINING.md](TRAINING.md).

---

## Install

```bash
uv sync
```

Python 3.12+. Runtime deps: `strands-agents`, `pydantic` v2, `openai`,
`pyyaml`. Optional extras: `[observers]` (Rich TUI), `[otel]`
(OpenTelemetry), `[gemini]`, `[huggingface]`,
`[dashboard]` (the editable `apps/dashboard/` install).

## Two-minute tour

**Inference — fan out two reasoners over a question.**

```python
import asyncio
from pydantic import BaseModel, Field
from operad import Configuration, Parallel
from operad.agents.reasoning import Reasoner

class Q(BaseModel): text: str = Field(default="", description="The user's question.")
class A(BaseModel): answer: str = Field(default="", description="Concise answer.")
class Report(BaseModel): answers: dict[str, str] = {}

cfg = Configuration(backend="llamacpp", host="127.0.0.1:8080", model="qwen2.5-7b")

root = Parallel(
    {"poet": Reasoner(config=cfg, input=Q, output=A, role="You are a poet."),
     "coder": Reasoner(config=cfg, input=Q, output=A, role="You write Python.")},
    input=Q, output=Report,
    combine=lambda r: Report(answers={k: v.answer for k, v in r.items()}),
)

async def main():
    await root.abuild()
    out = await root(Q(text="Write something about concurrency."))
    print(out.response, out.run_id, out.latency_ms)

asyncio.run(main())
```

`build()` walks the tree, type-checks every edge, resolves the model
backend, and returns a computation graph — all *before* a single token
is generated. Every invocation returns an `OperadOutput[Out]` envelope
with `run_id`, `agent_path`, `latency_ms`, token counts, and stable
`hash_*` fingerprints for reproducibility.

**Training — a fit loop in 10 lines.**

```python
from operad.optim import CriticLoss, TextualGradientDescent
from operad.train import Trainer
from operad.data import DataLoader, random_split

agent.mark_trainable(role=True, task=True, rules=True)
await agent.abuild()

train, val = random_split(dataset, [0.8, 0.2])
loader     = DataLoader(train, batch_size=8, shuffle=True)

trainer = Trainer(agent,
                  TextualGradientDescent(agent.parameters(), lr=1.0),
                  CriticLoss(rubric_critic))
report  = await trainer.fit(loader, val_ds=val, epochs=5)
```

Gradients are LLM critiques in natural language; `backward()` walks
the runtime tape; `RewriteAgent`s apply them to the agent's
`Parameter`s. Walkthrough in [TRAINING.md](TRAINING.md).

## Project layout

```
operad/        — the library (types, build, agents, algorithms, optim, train, runtime…)
apps/          — surrounding apps: dashboard, studio, demos
examples/      — runnable scripts, one per major abstraction
scripts/       — verify.sh = full offline test suite + example sweep
tests/         — offline unit tests + opt-in integration suite
```

Each directory has its own README. Start with
[`operad/README.md`](operad/README.md) for the library tour, or jump
straight into a submodule:
[`operad/core/`](operad/core/README.md) ·
[`operad/agents/`](operad/agents/README.md) ·
[`operad/algorithms/`](operad/algorithms/README.md) ·
[`operad/optim/`](operad/optim/README.md) ·
[`operad/train/`](operad/train/README.md) ·
[`operad/runtime/`](operad/runtime/README.md).

## Writing an agent

A leaf agent declares its contract on the class body:

```python
from pydantic import BaseModel
from operad import Agent, Configuration

class Q(BaseModel): text: str
class A(BaseModel): answer: str

class Concise(Agent[Q, A]):
    input  = Q
    output = A
    role   = "You are terse."
    task   = "Answer the question in one sentence."
    rules  = ("Never exceed 20 words.",)

leaf = Concise(config=Configuration(backend="llamacpp",
                                    host="127.0.0.1:8080",
                                    model="qwen2.5-7b"))
```

Compose leaves with `Pipeline` (sequential), `Parallel` (fan-out), or
`Switch` (runtime routing). For the full component library — domain
folders for reasoning, coding, conversational, memory, retrieval,
safeguard, debate — see
[`operad/agents/README.md`](operad/agents/README.md).

## Writing an algorithm

Algorithms orchestrate agents through outer loops with metric
feedback. They are plain classes with custom `run(...)` signatures —
not `Agent` subclasses.

```python
from operad.algorithms import BestOfN
from operad.metrics import RubricCritic

bon  = BestOfN(generator=reasoner, critic=RubricCritic(critic), n=5)
best = await bon.run(Q(text="..."))
```

Components vs. algorithms is a load-bearing distinction — see
[`operad/algorithms/README.md`](operad/algorithms/README.md).

## Train an agent

Every mutable field on an `Agent` is a `Parameter`; every `Metric`
lifts to a `Loss`; the spine is `Parameter → tape → backward →
Optimizer → Trainer`. Optimizers in the fleet:
`TextualGradientDescent`, `MomentumTextGrad`, `EvoGradient`,
`OPROOptimizer`, `APEOptimizer`. Full walkthrough:
[TRAINING.md](TRAINING.md). Design doc:
[`operad/optim/README.md`](operad/optim/README.md).

## CLI & YAML

Run an agent end-to-end from a YAML config without writing Python:

```yaml
# examples/config-react.yaml
agent: operad.agents.reasoning.react.ReAct
config:
  backend: llamacpp
  host: 127.0.0.1:8080
  model: qwen2.5-7b-instruct
  temperature: 0.3
runtime:
  slots:
    - backend: llamacpp
      host: 127.0.0.1:8080
      limit: 8
```

```bash
uv run operad run   examples/config-react.yaml --input examples/task.json
uv run operad trace examples/config-react.yaml
uv run operad graph examples/config-react.yaml --format json
uv run operad tail  run.jsonl --speed=0
```

`run` validates the input JSON against the agent's `input` model,
builds the graph, invokes, and prints the `Out` as JSON. `trace`
prints the Mermaid rendering. `graph` dumps it as JSON. `tail`
replays a recorded NDJSON trace. See
[`operad/configs/README.md`](operad/configs/README.md).

## Apps

| Command                | Port  | What it does                                                         |
| ---------------------- | ----- | -------------------------------------------------------------------- |
| `uv run operad-dashboard --port 7860` | 7860 | Live event stream, graph view, fitness/mutation/drift/training panels per `run_id`. See [`apps/dashboard/`](apps/dashboard/README.md). |
| `uv run operad-studio --port 7870 --data-dir … --agent-bundle …` | 7870 | Human-feedback labeling + relaunch `Trainer.fit` with `HumanFeedbackLoss`. See [`apps/studio/`](apps/studio/README.md). |
| `uv run python apps/demos/agent_evolution/run.py --offline` | — | Fully-offline showcase: a seed agent evolved over generations. See [`apps/demos/`](apps/demos/README.md). |
| `uv run --extra observers python demo.py` | — | ~30-second Rich-formatted end-to-end (prompts, graph, invoke, trace, mutation diff). `--offline` runs the schema-only stages without a server. |

The dashboard and studio are independent editable installs in this
monorepo — they consume `operad` like external users.

## Self-hosted observability (Langfuse + OTel)

A `docker-compose.yml` at the repo root brings up Langfuse v3
alongside both apps with one command. operad's `OtelObserver` already
emits a hierarchical span tree (one span per `(run_id, agent_path)`,
nested per the agent topology) and aligns the OTel `trace_id` with
operad's `run_id`, so the dashboard's run-detail page renders a
"View in Langfuse" link that resolves directly to the matching trace
without any external mapping.

```bash
cp .env.example .env
# Set LANGFUSE_INIT_PROJECT_*_KEY pair + user password in .env, then:
bash scripts/langfuse_otel_header.sh --update    # populates OTEL_EXPORTER_OTLP_HEADERS
docker compose up -d
```

Exposed: Langfuse on **3000**, dashboard on **7860**, studio on
**7870**. The stack also includes Postgres, Clickhouse, Redis, and
MinIO (S3-compatible blob); expect ~3 GB RAM. See
[`apps/README.md`](apps/README.md) for details.

## Tests

```bash
uv run pytest tests/                    # offline unit tests
bash   scripts/verify.sh                # tests + every offline example + demo.py --offline
```

Integration tests are opt-in via `OPERAD_INTEGRATION=<backend>`; one
backend at a time. The matrix and per-backend env vars live in
[INVENTORY.md §17](INVENTORY.md#17-cassette-based-offline-tests) and
the per-adapter docs under
[`operad/core/models.py`](operad/core/models.py).

## License

See [LICENSE.txt](LICENSE.txt).
