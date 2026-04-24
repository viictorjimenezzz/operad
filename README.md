# operad

**Typed, composable agent architectures with PyTorch-style training for local-first LLM servers.**
Agents are Python modules in the `torch.nn` sense: you build them, nest
them, trace them, and run them against local or hosted LLMs. Composition
is the whole mental model — hence the name.

```python
import asyncio
from pydantic import BaseModel, Field
from operad import Configuration, Parallel, Pipeline
from operad.agents.reasoning import Reasoner

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

For the full feature catalog see [FEATURES.md](FEATURES.md). For the
design rationale see [VISION.md](VISION.md).

## Why the name

An **operad** is the mathematical structure of abstract operations that
compose by trees: `n`-ary operations whose outputs plug into the inputs
of other operations, with the whole composition obeying the obvious
associativity laws. That is precisely what this library builds: every
`Agent[In, Out]` is a typed operation; `Pipeline` and `Parallel` wire
them together; `build()` captures the resulting tree as a first-class
object you can inspect, export, mutate, and run.

## Install

```bash
uv sync
```

Python 3.12+. Runtime deps are
[strands-agents](https://strandsagents.com/), pydantic v2, and the
`openai` SDK (pulled in by Strands' OpenAI-compatible adapters).
Optional extras: `[observers]` (Rich TUI), `[otel]` (OpenTelemetry),
`[gemini]`, `[huggingface]`.

## Play the demo

One command, no model server required:

```bash
uv run python apps/demos/agent_evolution/run.py --offline
```

A seed agent evolves over a handful of generations; the fitness curve
climbs; the before/after diff prints at the end. Add `--dashboard`
(after starting `operad-dashboard --port 7860` in another terminal)
to watch it live. See
[apps/demos/agent_evolution/README.md](apps/demos/agent_evolution/README.md)
for the story.

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

**Each component ships a `default_sampling` dict.** Class-level
opinions (e.g. `Classifier` → `temperature=0.0`) merge into the
caller's `Configuration` at construction; user-explicit fields
always win.

**`build()` symbolically traces the architecture**, type-checking every
parent-to-child handoff before any model is contacted. Out pops an
`AgentGraph`. Built graphs can be `freeze()`-ed to disk and `thaw()`-ed
elsewhere to skip the symbolic trace (useful for CLIs, Lambdas, tests).

**Agents are trainable.** Every mutable field on an Agent —
`role`, `task`, `rules`, `examples`, sampling knobs — is a
`Parameter`. `operad.optim` ships `TextualGradientDescent`,
`MomentumTextGrad`, `EvoGradient`, `OPROOptimizer`, and
`APEOptimizer` (subclasses of a shared `Optimizer` base), plus
`operad.train.Trainer`, which wraps fit/evaluate/predict with
callbacks and LR schedulers. See [TRAINING.md](TRAINING.md).

**Components compose; algorithms orchestrate.** Everything in
`operad.agents` is an `Agent[In, Out]` that nests freely. Everything
in `operad.algorithms` is a plain class that takes Agents as parameters
and closes a loop over their outputs (`BestOfN`, `Debate`, `SelfRefine`,
`VerifierLoop`, `Evolutionary`, `Sweep`, `AutoResearcher`).

**Metrics are either pure Python or Agents.** A rubric-driven LLM
judge is a `Critic`, which is an `Agent[Candidate[In, Out], Score]` —
the same `build()` story applies.

## Run the demo

```bash
# 1. Start a local llama-server on 127.0.0.1:9000 serving your model.
# 2. Then:
uv run --extra observers python demo.py
```

`demo.py` is a ~30-second, Rich-formatted showcase: rendered prompts,
Mermaid graph, live invocation, trace dump, and a mutation diff. Pass
`--offline` to run only the schema-only stages (rendered prompts,
Mermaid graph, mutation diff) with no server. To exercise the full
offline surface — the test suite plus every offline-capable example
plus `demo.py --offline` — run `bash scripts/verify.sh`.

Every network-backed example in `examples/` uses the same canonical
target via `examples/_config.py` — set `OPERAD_LLAMACPP_HOST` and
`OPERAD_LLAMACPP_MODEL` to override host or model.

## Train an agent

Every field that matters — `role`, `task`, `rules`, `examples`,
sampling — is a first-class `Parameter`. Pick a loss, an optimizer,
and a trainer, and you have a real fit loop:

```python
from operad import Pipeline
from operad.optim import CriticLoss, TextualGradientDescent
from operad.optim.lr_scheduler import CosineExplorationLR
from operad.train import Trainer
from operad.data import DataLoader, random_split

agent = Pipeline(Planner(...), Reasoner(...), Critic(...))
agent.mark_trainable(role=True, task=True, rules=True)
await agent.abuild()

train, val = random_split(dataset, [0.8, 0.2])
loader     = DataLoader(train, batch_size=8, shuffle=True)

loss_fn   = CriticLoss(rubric_critic)
optimizer = TextualGradientDescent(agent.parameters(), lr=1.0)
scheduler = CosineExplorationLR(optimizer, T_max=10)

trainer = Trainer(agent, optimizer, loss_fn, scheduler=scheduler)
report  = await trainer.fit(loader, val_ds=val, epochs=5)
```

`TextualGradient` is a Pydantic critique, not a float; `backward()`
walks the runtime tape, and every `Parameter` that took blame gets
rewritten by its optimizer. Full walkthrough in
[TRAINING.md](TRAINING.md).

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
uv run operad tail  run.jsonl --speed=0
```

`run` validates the input JSON against the agent's `input` model, builds
the graph, invokes, and prints the `Out` as JSON. `trace` prints the
Mermaid rendering of the built graph; `graph` dumps it as JSON;
`tail` replays a recorded NDJSON trace.

## Examples

One narrative example per major abstraction, in `examples/`:

- `parallel.py`, `pipeline.py`, `federated.py` — structural composition.
- `react.py`, `router_switch.py` — reasoning patterns.
- `best_of_n.py`, `evolutionary_demo.py`, `sweep_demo.py` — algorithms.
- `talker.py`, `pr_reviewer.py`, `memory_demo.py` — per-domain composites.
- `custom_agent.py` — minimal user-defined `Agent[In, Out]` subclass.
- `sandbox_tooluser.py`, `sandbox_add_tool.py`, `sandbox_pool_demo.py` —
  isolated process-pool tool execution.
- `observer_demo.py` — trace + Rich dashboard observers in action.
- `eval_loop.py` — `evaluate(agent, dataset, metrics)` end-to-end.
- `mermaid_export.py` — **offline** demo: `build()` a small composite
  and print its Mermaid graph.

All network-requiring examples read `OPERAD_LLAMACPP_HOST` /
`OPERAD_LLAMACPP_MODEL`; `mermaid_export.py` runs without a model.

## Tests

```bash
uv run pytest tests/
```

### Integration tests (opt-in)

Gated by `OPERAD_INTEGRATION=<backend>`; never run in CI by default. One
backend at a time — each test skips unless its specific value is set.

| Backend     | `OPERAD_INTEGRATION` | Required env        | Optional env (with defaults)                                                   |
| ----------- | -------------------- | ------------------- | ------------------------------------------------------------------------------ |
| llamacpp    | `llamacpp`           | —                   | `OPERAD_LLAMACPP_HOST` (`127.0.0.1:8080`), `OPERAD_LLAMACPP_MODEL` (`default`) |
| lmstudio    | `lmstudio`           | —                   | `OPERAD_LMSTUDIO_HOST` (`127.0.0.1:1234`), `OPERAD_LMSTUDIO_MODEL` (`default`) |
| ollama      | `ollama`             | —                   | `OPERAD_OLLAMA_HOST` (`127.0.0.1:11434`), `OPERAD_OLLAMA_MODEL` (`llama3.2`)   |
| openai      | `openai`             | `OPENAI_API_KEY`    | `OPERAD_OPENAI_MODEL` (`gpt-4o-mini`)                                          |
| anthropic   | `anthropic`          | `ANTHROPIC_API_KEY` | `OPERAD_ANTHROPIC_MODEL` (`claude-haiku-4-5`)                                  |
| gemini      | `gemini`             | `GEMINI_API_KEY`    | `OPERAD_GEMINI_MODEL` (`gemini-1.5-flash`)                                     |
| huggingface | `huggingface`        | —                   | `OPERAD_HF_MODEL` (`HuggingFaceTB/SmolLM2-135M`)                               |
| batch       | `batch`              | `OPENAI_API_KEY`    | `OPERAD_OPENAI_MODEL`                                                          |

## Layout

```
operad/
  core/              Agent, Example, Configuration, build, freeze, graph,
                     models (all backend adapters), render, state
  utils/             errors, hashing, ops (typed in-place mutations),
                     paths, cassette (record/replay)
  runtime/           slots (concurrency + RPM/TPM), trace, trace_diff,
                     replay, streaming, retry, observers (Rich/OTel/JSONL),
                     launchers (subprocess + pool)
  agents/            the torch.nn-style library, organised by domain:
    pipeline.py      structural operators (domain-agnostic)
    parallel.py
    reasoning/       Reasoner, Actor, Extractor, Evaluator, Classifier,
                     Planner, Critic, Reflector, Retriever, Router,
                     ToolUser + ReAct composition
    coding/          CodeReviewer, DiffSummarizer, PRReviewer, ContextOptimizer
    conversational/  Persona, Safeguard, TurnTaker, Talker, RefusalLeaf
    memory/          BeliefExtractor, EpisodicSummarizer, UserModelExtractor
    safeguard/       InputSanitizer, OutputModerator (task-agnostic)
  algorithms/        AutoResearcher, BestOfN, Debate, SelfRefine,
                     VerifierLoop, Evolutionary, Sweep
  benchmark/         Dataset, Entry, AggregatedMetric, evaluate, EvalReport
  metrics/           Metric protocol, ExactMatch, JsonValid, Latency,
                     Contains, RegexMatch, Rouge1, RubricCritic, CostTracker
  optim/             Parameter, TextualGradient, tape()/backward(),
                     Loss + CriticLoss + LossFromMetric,
                     Optimizer fleet (TextualGradientDescent,
                     MomentumTextGrad, EvoGradient, OPROOptimizer,
                     APEOptimizer), lr_scheduler family,
                     BackpropAgent, RewriteAgent
  train/             Trainer (fit/evaluate/predict), callbacks
                     (EarlyStopping, BestCheckpoint, GradClip,
                     PromptDrift, LearningRateLogger, MemoryRotation),
                     EpochReport / TrainingReport
  data/              DataLoader, Batch, Sampler family, random_split
  cli.py             operad run/trace/graph/tail
  tracing.py         watch() context manager + OPERAD_TRACE env
tests/               offline tests + opt-in integration
examples/
```

## License

See [LICENSE.txt](LICENSE.txt).
