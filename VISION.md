# operad — vision

> *Audience: coding agents and contributors. This document is terse,
> structured, and link-dense by design. For the user-facing intro, see
> [README.md](README.md). For the capability inventory, see
> [INVENTORY.md](INVENTORY.md). For training internals, see
> [TRAINING.md](TRAINING.md) and
> [`operad/optim/README.md`](operad/optim/README.md).*

---

## 1. Purpose

`operad` is an agentic framework built on top of
[strands-agents](https://strandsagents.com/). It inherits everything
strands gives you for free — tool calls, MCP, structured output,
OpenAI-compatible adapters across every common backend — and adds
three capabilities strands does not provide:

- **Typed compositional definition** of agentic systems.
- **Prompt parametrization** — every prompt field is a tunable knob.
- **Algorithms** — outer loops where agents improve other agents.

Together, these enable the end vision: **dynamic agentic systems
trained at the prompt level, not the weights level** — improvement
driven by text feedback, textual backpropagation, and prompt
engineering as optimization. Anyone building an agentic workflow can
build it on `operad` and then launch coordinated-agent algorithms on
their workflow to improve it.

This framing dictates the rest of the architecture. Every primitive
exists because it serves prompt-level training. Every dependency
points toward making improvement loops first-class citizens.

## 2. The three pillars

### 2.1 Typed compositional definition

`Agent[In, Out]` is a typed unit of work. `Sequential`, `Parallel`,
`Switch`, and `Router` compose units into trees. `build()` walks the
tree symbolically, type-checks every parent-to-child handoff, and
freezes the result into an `AgentGraph` — a first-class value you can
export, mutate, hash, replay.

*Why this matters for the vision*: an agentic system you cannot
introspect is one you cannot improve. The graph is the substrate every
optimizer, observer, and replay tool reads. Topology errors are caught
before any token is generated; the same graph drives Mermaid export,
cassette replay, cost accounting, and `backward()`. **The build step
is the compile step**: it turns a Python script into a data structure.

### 2.2 Prompt parametrization

Every mutable field on an `Agent` is a `Parameter`:

- `role`, `task` → `TextParameter`
- `rules` → `RuleListParameter`
- `examples` → `ExampleListParameter`
- `temperature`, `top_p` → `FloatParameter`
- `model`, `backend`, `renderer` → `CategoricalParameter`

`agent.parameters()` and `agent.named_parameters()` yield handles you
can read, mutate, sweep, A/B test, or train. `mark_trainable(...)`
flips `requires_grad` flags at any granularity (whole tree, per field,
per dotted path).

*Why this matters for the vision*: prompts cease to be opaque strings
and become a tunable surface. This is the precondition for treating
"prompt engineering" as a numerical (well, *textual*) optimization
problem instead of a hand-craft discipline. Constraints
(`TextConstraint`, `VocabConstraint`, `NumericConstraint`,
`ListConstraint`) are the textual-gradient analog of gradient
clipping, applied before every update.

### 2.3 Algorithms — agents improving agents

`operad/algorithms/` are plain classes whose `run(...)` methods
orchestrate `Agent`s through outer loops with metric feedback
(`Beam`, `Debate`, `Sweep`, `SelfRefine`, `AutoResearcher`). They
are deliberately **not** `Agent` subclasses — their natural API is
not `__call__(x: In) -> Out`.

`operad/optim/` and `operad/train/` formalize the same pattern: the
gradient agents (`BackpropAgent`) and rewrite agents (`RewriteAgent`)
that constitute `backward()` and `Optimizer.step()` are themselves
`Agent` subclasses. So the whole observer / cassette / hashing stack
composes straight through a fit loop.

*Why this matters for the vision*: improvement is itself an agentic
workflow. There is no separate optimization framework underneath;
the same primitives that build the workflow also improve it. This is
what makes "people who build agentic workflows can launch algorithms
on their workflows" coherent — the algorithms are made of the same
stuff as the workflow they improve.

## 3. The training paradigm

Prompt-level training is operad's load-bearing differentiator.

**The signal is text.** A `TextualGradient` is a Pydantic critique:

```python
class TextualGradient(BaseModel):
    message: str                    # natural-language critique
    by_field: dict[str, str] = {}   # per-field breakdown
    severity: float = 1.0           # magnitude; 0 = no-op
    target_paths: list[str] = []    # blame-routing hints
```

LLM critics (rubric judges, structured evaluators) emit gradients;
optimizers consume them; `RewriteAgent`s apply them to `Parameter`s.

**The plumbing mirrors PyTorch's:** `Parameter` → `tape()` →
`backward()` → `Optimizer.step()` → `Trainer.fit()`. The mirroring is
ergonomic — anyone who has trained a model can read the code — but
it is not the *reason* the architecture exists. The reason is that
the same observer / cassette / hashing infrastructure that makes
inference observable also makes training observable, and the same
`Agent` surface that runs the workflow also implements the optimizer.

**Optimizer fleet.** `TextualGradientDescent`, `MomentumTextGrad`,
`EvoGradient` (population-search), `OPROOptimizer` (LLM-as-optimizer
with history), `APEOptimizer` (sample-and-rank). All five subclass
the same `Optimizer` base; all five take `list[Parameter] |
list[ParamGroup]`; all five expose `zero_grad()` + `await step()`.

**Config as a unit.** `mark_trainable(config=True)` lifts the entire
`Configuration` block (backend, model, sampling, renderer, …) into a
single `ConfigurationParameter`. A `ConfigurationConstraint` encodes
per-backend legality (`allowed_models[backend]`), sampling ranges, and
advisory budget knobs (`max_tokens_per_run`, `max_cost_per_run_usd`)
that flow into `apply_rewrite` via an optional `cost_estimator`
callable. Optimisers can now reason about the config holistically —
e.g. "the gradient says we're too slow; downshift backend and lower
`max_tokens` together" — instead of correlating five independent leaf
parameters. `EvoGradient` consumes this surface via the
`SetConfiguration` op + `random_configuration_op` factory, sampling
legal configurations from the constraint pool.

**Trainer.** `operad.train.Trainer.fit/evaluate/predict` glues the
spine together with callbacks (`EarlyStopping`, `BestCheckpoint`,
`GradClip`, `PromptDrift`, `LRLogger`, `MemoryRotation`,
`HumanFeedbackCallback`) and LR schedulers. Full walkthrough in
[TRAINING.md](TRAINING.md).

**Meta-optimization** is the long-term research surface: an optimizer
*is* an agent, so a `Trainer` optimizing the optimizer that optimizes
a workflow is the same three-level stack you get with learned
optimizers — except the gradient language is English.

## 4. Strands as the substrate

We deliberately do not reimplement what strands already does well:

| Provided by strands              | Provided by operad                     |
| -------------------------------- | -------------------------------------- |
| Tool calls, MCP                  | Typed `Agent[In, Out]` over strands    |
| Structured output                | `Sequential` / `Parallel` / `Switch`     |
| OpenAI-compatible adapters       | `build()` symbolic trace + type check  |
| Backend selection                | `Parameter` + textual gradients        |
| Conversation state               | `Trainer` + callbacks + LR schedulers  |
| Streaming                        | Algorithms (`Beam`, `Debate`, …)       |
| Provider auth                    | Observer registry + cassette replay    |

Supported backends today: `llamacpp`, `lmstudio`, `ollama`,
`huggingface`, `openai`, `anthropic`, `bedrock`, `gemini`. Batch mode
on the three providers that expose it (`openai`, `anthropic`,
`bedrock`).

## 5. Architecture map

Current state. See [`operad/README.md`](operad/README.md) for the
rationale of every submodule and links to per-submodule READMEs.

| Submodule         | Role                                                                              |
| ----------------- | --------------------------------------------------------------------------------- |
| `core/`           | `Agent`, `build`, `AgentGraph`, `Configuration`, model dispatch, freeze/diff      |
| `utils/`          | hashing, errors, mutation primitives (`Op`/`CompoundOp`), cassette record/replay  |
| `runtime/`        | concurrency slots, traces, observer registry (Rich/JSONL/OTel/Web), cost, retry, sandbox launcher |
| `agents/`         | the component library: `reasoning/`, `coding/`, `conversational/`, `memory/`, `retrieval/`, `safeguard/`, `debate/` + `Sequential` / `Parallel` |
| `algorithms/`     | `Beam`, `Debate`, `Sweep`, `SelfRefine`, `AutoResearcher`                         |
| `metrics/`        | deterministic scorers + `LLMAAJ` + `CostTracker`                            |
| `benchmark/`      | `Dataset`, `Entry`, `evaluate`, `Experiment`, `SensitivityReport`, `RegressionReport` |
| `data/`           | `DataLoader`, samplers (incl. `UncertaintySampler`), `random_split`               |
| `optim/`          | `Parameter` + `tape`/`backward` + `Optimizer` fleet + LR schedulers + `BackpropAgent` / `RewriteAgent` |
| `train/`          | `Trainer` + callbacks + `HumanFeedbackCallback` / `HumanFeedbackLoss` + `TrainerProgressObserver` |
| `configs/`        | YAML loader + schema (drives the CLI)                                             |
| `cli.py`          | `operad run` / `trace` / `graph` / `tail`                                         |
| `tracing.py`      | `watch()` context + `OPERAD_TRACE` env entry                                      |
| `dashboard.py`    | event POST helper for a running `apps/dashboard/`                                 |

Surrounding extras live outside `operad/`:
[`apps/dashboard`](apps/dashboard/README.md),
[`apps/studio`](apps/studio/README.md),
[`apps/demos`](apps/demos/README.md),
[`examples/`](examples/README.md),
[`scripts/verify.sh`](scripts/verify.sh).

## 6. Roadmap

Items not yet in code, ordered by priority:

1. ~~**Cassette-replay determinism validation**~~ — done in stream 5-2;
   `training_cassette_context` records/replays at the optimizer-step
   level (`*.train.jsonl`), yielding byte-equal `TrainingReport`s.
2. **Pre-wired composition wrappers** at `operad/agents/reasoning/`:
   `debate.py` and `verifier.py`. The corresponding algorithms exist
   under `operad/algorithms/`; the agent-level pre-wirings (parallel
   to `react.py`) do not.
3. **Additional launchers** in `operad/runtime/launchers/`: asyncio
   default + macOS Terminal. Today only the sandbox process pool ships.
4. **More algorithms**: `SelfRefine`, `TalkerReasoner`.
5. **`TurnTaker`** under `operad/agents/conversational/`.
6. **Meta-optimization** — north-star research surface. An optimizer
   is itself an `Agent`; a `Trainer` optimizing the optimizer that
   optimizes a workflow is the long-term unlock.
7. **`AutoResearcher` on 8 concurrent llama-server slots**, fully
   observable in a live dashboard, with per-agent metrics feeding an
   outer best-of-N loop. End-to-end milestone for the local-first
   story.

## 7. Non-goals

- **No model-weight training.** operad trains *prompts and sampling*,
  not weights. We are not an LLM training framework.
- **No static-type-checker runtime integration** (`ty`, `mypy`).
  PEP-561 typing for IDE/CI; `build()` does dynamic validation. No
  shelling out to type checkers.
- **No prompt templating engine in the foundations.** `role`, `task`,
  `rules` are plain strings; the built-in renderer emits XML / Markdown
  / chat-template. If Jinja-style templating is needed later it slots
  in by overriding `Agent.format_system_message` — the foundations do
  not change.
- **No agent DSL or YAML/JSON blueprint system in the foundations.**
  The CLI's YAML loader (`operad/core/config.py`) is a thin deserializer
  over the Python API, not a separate language.
- **No hidden model-provider fallbacks.** `Configuration.backend` is
  the single source of truth. Provider resolution happens explicitly
  in `operad/core/models.py`.

## 8. Contributor checklist

When adding to the library:

1. **Preserve the components-vs-algorithms split.** A typed `In → Out`
   contract ⇒ the new abstraction is an `Agent` subclass and lives in
   `operad/agents/<domain>/components/`. An orchestrator with a
   feedback loop whose natural API is not `__call__(x)` ⇒ a plain
   class with a `run(...)` method living in `operad/algorithms/`.

2. **Declare component contracts as class attributes.** `input`,
   `output`, `role`, `task`, `rules`, `examples` all live on the class
   body. Construction kwargs override; instance mutation works.

3. **Composite `forward` is a router, not a calculator.** Inspect
   payload values only inside leaves or post-invoke. The sentinel
   proxy in `operad/core/build.py` catches payload-branching at trace
   time and raises `BuildError`.

4. **`__init__` is side-effect-free.** No network, no provider
   handshakes, no model loading. All of that belongs in `build()`.

5. **Add offline tests.** Use `FakeLeaf`-style helpers — anything that
   overrides `forward` skips strands wiring and runs in the test
   process without network. Integration tests are opt-in via
   `OPERAD_INTEGRATION=<backend>`.

6. **Extend, don't fork.** New abstractions slot into:
   - `operad/agents/<domain>/components/` for components,
   - `operad/algorithms/` for orchestrators,
   - `operad/metrics/` for scorers,
   - `operad/optim/` for optimizers / losses / schedulers,
   - `operad/runtime/observers/` for observability,
   - `operad/data/` for samplers,
   - `operad/core/models.py` for backend adapters.

   Foundations under `operad/core/` and `operad/utils/` should rarely
   change.

7. **Update the inventory.** Anything new that ends up in the public
   API surface gets an entry in [INVENTORY.md](INVENTORY.md).
