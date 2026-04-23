# operad

**Typed, composable agent architectures for local-first LLM servers.**
Agents are Python modules in the `torch.nn` sense: you build them, nest
them, trace them, and run them against local or hosted LLMs. Composition
is the whole mental model — hence the name.

```python
import asyncio
from pydantic import BaseModel, Field
from operad import Configuration, Parallel, Reasoner

class Q(BaseModel): text: str = Field(default="", description="The user's question.")
class A(BaseModel): answer: str = Field(default="", description="Concise answer.")
class Report(BaseModel): answers: dict[str, str] = {}

cfg = Configuration(backend="llamacpp", host="127.0.0.1:8080", model="your-model")

root = Parallel(
    {
        "poet":  Reasoner(config=cfg, input=Q, output=A, role="You are a poet."),
        "coder": Reasoner(config=cfg, input=Q, output=A, role="You write Python."),
    },
    input=Q, output=Report,
    combine=lambda r: Report(answers={k: v.answer for k, v in r.items()}),
)

async def main():
    await root.abuild()
    out = await root(Q(text="Write something about concurrency."))
    print(out.response)  # the typed Out
    print(out.run_id, out.hash_input, out.latency_ms)  # reproducibility + timing

asyncio.run(main())
```

Every invocation returns an `OperadOutput[Out]`: `out.response` is the
user's typed payload, and the envelope carries `run_id`, `agent_path`,
`latency_ms`, optional `prompt_tokens` / `completion_tokens`, plus a
stable `hash_*` fingerprint (model, prompt, graph, input, schema) for
reproducibility.

That's the whole program. `build()` walks the tree, resolves the model
backend, checks every typed edge, and returns a computation graph you
can export as Mermaid or JSON — all *before* a single token is generated.
The system prompt is rendered from each Agent's `role`, `task`, `rules`,
`examples`, and — DSPy-style — every `Field(description=...)` on your `In`
and `Out` classes gets threaded into the model's context.

For the full design rationale, see [VISION.md](VISION.md).

## Why the name

An **operad** is the mathematical structure of abstract operations that
compose by trees: `n`-ary operations whose outputs plug into the inputs
of other operations, with the whole composition obeying the obvious
associativity laws. That is precisely what this library builds: every
`Agent[In, Out]` is a typed operation; `Pipeline` and `Parallel` wire
them together; `build()` captures the resulting tree as a first-class
object you can inspect, export, mutate, and run.

## Status

Foundations + runtime + first components (iterations 1–3):

- `Agent[In, Out]` with class-level defaults (`role`, `task`, `rules`,
  `examples`, `input`, `output`) — a single class, no separate `Prompt`
  wrapper.
- Typed `Example[In, Out]` few-shot pairs.
- XML-tagged prompt renderer that surfaces `Field(description=...)` from
  user-defined `In` and `Out` and from library-internal section metadata.
- `operad.agents` — the `torch.nn`-style library, organized by domain:
  structural operators (`Pipeline`, `Parallel`) at the top level and
  per-domain subfolders for leaves + composed patterns. Ships the
  `reasoning/` domain with seven leaves (`Reasoner`, `Actor`,
  `Extractor`, `Evaluator`, `Classifier`, `Planner`, `Critic`) and the
  `ReAct` composition.
- `operad.algorithms` — `BestOfN` (plain class with `run(x)`),
  `Candidate`, `Score`. *Algorithms are not Agents*: they orchestrate
  agents with metric feedback; their API shape is whatever the
  algorithm needs.
- `operad.models` — per-backend resolvers: `llamacpp`, `lmstudio`,
  `ollama`, `openai`, `bedrock`.
- `operad.runtime.slots` — per-endpoint concurrency limits.
- `operad.metrics` — `Metric` protocol, `ExactMatch`, `JsonValid`,
  `Latency`.
- `operad.core.graph` — `to_mermaid`, `to_json`.
- Offline test suite, opt-in integration test against a real
  llama-server.

What's **not** here yet (see [VISION.md §7](VISION.md#7-where-were-going)):
runtime observers + Rich dashboard, build-time sentinel proxy,
dataset-level `evaluate(...)`, more algorithms (`Debate`,
`VerifierLoop`, `Evolutionary`), tools / memory / retrieval.

## Install

```bash
uv sync
```

Python 3.12+. Runtime deps are
[strands-agents](https://strandsagents.com/), pydantic v2, and the
`openai` SDK (pulled in by Strands' OpenAI-compatible adapters for
llama-server / LM Studio / Ollama / OpenAI).

## Core ideas

**An `Agent` is a `strands.Agent` subclass with typed I/O.** Composites
override `forward()`; leaves use the default, which does a single
structured-output call.

**Everything an agent needs lives on the agent itself** — `config`,
`role`, `task`, `rules`, `examples`, `input`, `output`. No separate
`Prompt` wrapper. Mutate them in place, serialize them, sweep over them.

**Components declare their contract as class attributes.** A subclass
of `Reasoner` / `Classifier` / `Extractor` sets `input`, `output`, and
any prompt-level overrides at the class level; instantiation is
`Leaf(config=cfg)`.

**`build()` symbolically traces the architecture**, type-checking every
parent-to-child handoff before any model is contacted. Out pops an
`AgentGraph`.

**Components compose; algorithms orchestrate.** Everything in
`operad.agents` is an `Agent[In, Out]` that nests freely. Everything
in `operad.algorithms` is a plain class that takes Agents as parameters
and closes a loop over their outputs.

**Metrics are either pure Python or Agents.** A rubric-driven LLM
judge is a `Critic`, which is an `Agent[Candidate[In, Out], Score]` —
the same `build()` story applies.

## Run the demo

```bash
# 1. Start a local llama-server on 127.0.0.1:8080 with a model loaded.
# 2. Then:
uv run python examples/parallel.py
```

Set `OPERAD_LLAMACPP_HOST` and `OPERAD_LLAMACPP_MODEL` to point
somewhere else.

## Run from YAML

You can run an agent end-to-end without writing Python by pointing the
`operad` CLI at a YAML config:

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
```

`run` validates the input JSON against the agent's `input` model, builds
the graph, invokes, and prints the `Out` as JSON. `trace` prints the
Mermaid rendering of the built graph; `graph` dumps it as JSON.

## Examples

One narrative example per major abstraction, in `examples/`:

- `parallel.py` — fan-out over specialized `Reasoner`s with a combine step.
- `federated.py` — `Parallel` over heterogeneous backends (llamacpp + OpenAI) with per-endpoint slot budgets.
- `pipeline.py` — three-stage `Pipeline` (`Extractor -> Planner -> Evaluator`) with typed edges.
- `react.py` — standalone `ReAct`; prints the Mermaid graph before running.
- `best_of_n.py` — `BestOfN` algorithm over a `Reasoner` generator and `Critic` judge.
- `custom_agent.py` — minimal user-defined `Agent[In, Out]` subclass with seeded `examples=`.
- `mermaid_export.py` — **offline** demo: `build()` a small composite and print its Mermaid graph.

All network-requiring examples read `OPERAD_LLAMACPP_HOST` /
`OPERAD_LLAMACPP_MODEL`; `mermaid_export.py` runs without a model.

## Streaming

Set `Configuration(stream=True)` to consume token-level chunks from the
backend as they arrive. `agent.stream(x)` is an async iterator that
yields `ChunkEvent`s for each mid-run piece and terminates with the
same `OperadOutput[Out]` envelope you get from `await agent(x)`:

```python
from operad import Configuration, ChunkEvent, OperadOutput

cfg = Configuration(backend="llamacpp", host="127.0.0.1:8080",
                    model="qwen2.5-7b-instruct", stream=True)
leaf = await MyLeaf(config=cfg).abuild()

async for item in leaf.stream(MyIn(question="...")):
    if isinstance(item, ChunkEvent):
        print(item.text, end="", flush=True)
    else:
        final: OperadOutput = item
```

`await agent(x)` still returns a single `OperadOutput` when
`stream=True` — it consumes the stream internally and returns the
envelope. Observers receive a new `"chunk"` event kind for each piece;
`RichDashboardObserver` updates the agent's line in place. Backends
that do not support streaming fall back to a single-envelope yield.

## Tests

```bash
uv run pytest tests/
```

### Integration tests (opt-in)

Gated by `OPERAD_INTEGRATION=<backend>`; never run in CI by default. One
backend at a time — each test skips unless its specific value is set.

| Backend  | `OPERAD_INTEGRATION` | Required env   | Optional env (with defaults)                                          |
| -------- | -------------------- | -------------- | --------------------------------------------------------------------- |
| llamacpp | `llamacpp`           | —              | `OPERAD_LLAMACPP_HOST` (`127.0.0.1:8080`), `OPERAD_LLAMACPP_MODEL` (`default`)   |
| openai   | `openai`             | `OPENAI_API_KEY` | `OPERAD_OPENAI_MODEL` (`gpt-4o-mini`)                               |
| ollama   | `ollama`             | —              | `OPERAD_OLLAMA_HOST` (`127.0.0.1:11434`), `OPERAD_OLLAMA_MODEL` (`llama3.2`)      |
| lmstudio | `lmstudio`           | —              | `OPERAD_LMSTUDIO_HOST` (`127.0.0.1:1234`), `OPERAD_LMSTUDIO_MODEL` (`default`)    |

```bash
OPERAD_INTEGRATION=llamacpp \
OPERAD_LLAMACPP_HOST=127.0.0.1:8080 \
OPERAD_LLAMACPP_MODEL=qwen2.5-7b-instruct \
uv run pytest tests/integration -v

OPERAD_INTEGRATION=openai OPENAI_API_KEY=sk-... \
uv run pytest tests/integration/test_openai.py -v

OPERAD_INTEGRATION=ollama \
uv run pytest tests/integration/test_ollama.py -v

OPERAD_INTEGRATION=lmstudio \
uv run pytest tests/integration/test_lmstudio.py -v
```

## Layout

```
operad/
  core/              Agent, Example, Configuration, build, graph, render
  utils/errors.py    BuildError + BuildReason
  models/            resolve_model dispatcher + per-backend adapters
  runtime/slots.py   per-endpoint concurrency semaphores
  agents/            the torch.nn-style library, organized by domain:
    pipeline.py      structural operators (domain-agnostic)
    parallel.py
    reasoning/
      components/    Reasoner, Actor, Extractor, Evaluator,
                     Classifier, Planner, Critic
      react.py       Reason-Act-Observe-Evaluate composition
    # future: coding/, conversational/, memory/ ...
  algorithms/        BestOfN (plain class), Candidate, Score
  metrics/           Metric protocol, deterministic scorers
tests/               offline tests + opt-in integration
examples/
  parallel.py
```

New domains drop in as sibling folders: `coding/` for PR reviewers,
`conversational/` for safeguarded chat flows, `memory/` for belief /
user-info extractors, and so on. Each follows the same shape —
`<domain>/components/` for leaves, `<domain>/*.py` for composed
patterns — and can freely pull components from sibling domains
(`ReAct`'s `Reasoner` comes straight from
`reasoning/components/reasoner.py`).

## License

See [LICENSE.txt](LICENSE.txt).
