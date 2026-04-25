# operad — capability inventory

> *Audience: coding agents and contributors.*
> *Every entry below corresponds to code that exists today. Items not yet
> shipped are isolated under "Planned" subsections (§6, §7, §22). For
> design rationale see [VISION.md](VISION.md); for the user-facing intro
> see [README.md](README.md); for training internals see
> [TRAINING.md](TRAINING.md) and
> [`operad/optim/README.md`](operad/optim/README.md).*

This file is the agent-facing catalog of operad's surface. It is
table-heavy, signal-dense, and exhaustive by design.

---

## 1. The `Agent[In, Out]` primitive

Every agent carries its full contract on itself: `input`, `output`,
`role`, `task`, `rules`, `examples`, `config`, optional
`default_sampling`. Subclass for a component type, or instantiate
directly for one-off use.

```python
from pydantic import BaseModel, Field
from operad import Agent, Configuration

class Q(BaseModel): text: str = Field(description="The user's question.")
class A(BaseModel): answer: str = Field(description="Concise answer.")

class MyLeaf(Agent[Q, A]):
    input = Q
    output = A
    role = "You are terse."
    task = "Answer the question in one sentence."
    rules = ("Never exceed 20 words.",)

leaf = MyLeaf(config=Configuration(backend="llamacpp",
                                   host="127.0.0.1:8080",
                                   model="qwen2.5-7b"))
```

### Agent methods

| Method / property            | What it does                                                                  |
| ---------------------------- | ----------------------------------------------------------------------------- |
| `build()` / `abuild()`       | Symbolic trace + type-check; returns the same Agent with `_graph` populated.  |
| `invoke(x)` / `__call__(x)`  | Run once, return `OperadOutput[Out]`.                                         |
| `stream(x)`                  | Async-iterate chunk events; final item is the envelope.                       |
| `hash_content`               | 16-hex SHA of the agent's declared state — content-addressable identity.      |
| `forward_in(x)` / `forward_out(x, y)` | Pass-through hooks; override to redact / moderate / repair.          |
| `validate(x)`                | Raise `BuildError` if unbuilt or type-mismatched. Single pre-flight.          |
| `explain(x)`                 | Run with per-leaf scratchpad injection; prints DSPy-style chain-of-thought.   |
| `summary()`                  | One-paragraph overview (`ClassName: N leaves, hash=…, graph=…`).              |
| `__rich__()`                 | Structured tree for `rich.print(agent)`.                                      |
| `a >> b`                     | Build a `Pipeline(a, b)`; chains flatten (`a >> b >> c` → three stages).      |
| `freeze(path)` / `thaw(path)`| Persist a built graph to disk, reconstitute without re-tracing (secrets stripped). |
| `state()` / `load_state(…)`  | Snapshot / restore declared attributes. PyTorch-style aliases: `state_dict()` / `load_state_dict()`. |
| `clone()`                    | Deep copy of state, unbuilt.                                                  |
| `diff(other)`                | Structured `AgentDiff` between two agents.                                    |

## 2. Structural composition

`Pipeline` chains agents left-to-right; `Parallel` fans out to a dict
of children and combines results.

```python
from operad import Pipeline, Parallel
p = Pipeline(stage_a, stage_b, stage_c)               # In → Out pipeline
r = Parallel({"a": leaf_a, "b": leaf_b},              # dict fan-out
             input=InType, output=OutType,
             combine=lambda results: ...)
```

`Switch` routes at runtime based on a router leaf's typed choice;
lives in `operad.agents`.

## 3. `OperadOutput[Out]` — the return envelope

Every invocation returns a typed envelope carrying the response plus
reproducibility metadata:

```
run_id, agent_path, latency_ms, prompt_tokens, completion_tokens,
hash_model, hash_prompt, hash_graph, hash_input, hash_output_schema,
hash_config, metadata (retries, last_error, ...)
```

```python
out = await agent(x)
out.response              # typed Out
out.hash_input            # stable over identical inputs
out.metadata["retries"]   # 0 on first-try success
```

## 4. Build-time tracing

`build()` constructs a sentinel of `input` using Pydantic defaults,
walks the tree, type-checks every parent-child handoff, and returns an
`AgentGraph`. No model is contacted.

```python
await agent.abuild()
print(agent._graph.to_mermaid())    # flowchart diagram
print(agent._graph.to_json())       # dict you can serialise
```

Type mismatches raise `BuildError("input_mismatch", …)` with a Mermaid
fragment pointing at the failing edge:

```
BuildError(input_mismatch): at Pipeline.stage_1 → stage_2
    expected Question, got Utterance

--- mermaid ---
flowchart LR
    stage_1[Reasoner: Utterance → Answer] -->|FAIL| stage_2[Critic: Question → Score]
```

## 5. Freeze / thaw — skip the trace

For CLIs, Lambdas, and test fixtures where cold-start latency matters:

```python
await agent.abuild()
agent.freeze("/tmp/agent.json")                    # persist

# Later, possibly in a fresh interpreter:
from operad import Agent
agent = Agent.thaw("/tmp/agent.json")              # no re-trace
out = await agent(my_input)
```

Stored artefacts: `AgentGraph`, `AgentState`, rendered prompts. API
keys are stripped automatically.

## 6. The component library — `operad.agents`

Domain-organised leaves + composed patterns. Each domain ships under
`operad.agents.<domain>`:

### `reasoning/`
Leaves: `Reasoner`, `ChatReasoner`, `Actor`, `Classifier`, `Critic`,
`Evaluator`, `Extractor`, `Planner`, `Reflector`, `Retriever` (plus
`BM25Retriever` and `FakeRetriever` variants), `Router`, `ToolUser`.
Pre-wired composites: `ReAct` (in `react.py`), `Switch` (in
`switch.py`).

### `coding/`
`CodeReviewer`, `DiffSummarizer`, `ContextOptimizer`, and `PRReviewer`
top-level composite.

### `conversational/`
`Talker` (turn-level chat leaf), `ConversationTitler` (titles a whole
conversation), `InteractionTitler` (titles a single interaction).
Disambiguated as `ConversationalTalker` at the top-level
`operad.agents` re-export to avoid clashing with `safeguard.Talker`.

### `memory/`
`Beliefs` (belief-state manager), `User` (session-memory updater),
`MemoryStore` (typed key-value store consumed by both leaves).
Schemas: `BeliefItem`, `BeliefOp`, `BeliefOperation`, `SessionItem`,
`SessionOp`, `SessionOperation`, `SessionTarget`,
`SessionNamespace`, `SessionStatus`.

### `safeguard/`
Chat-scope guardrail leaves. `Context` evaluates whether a prompt is
in-scope (returns a `SafeguardCategory`); `Talker` produces a refusal
or pass-through response when called as a guard. Disambiguated as
`SafeguardTalker` at the top-level `operad.agents` re-export.

```python
from operad.agents.safeguard import Context, Talker as SafeguardTalker
guard_pipeline = Pipeline(Context(config=cfg), SafeguardTalker(config=cfg))
```

### `retrieval/`
`CitationGist` (extracts citations from text), `EvidencePlanner`
(plans evidence-gathering steps for a claim), `FactFilter` (filters
candidate facts by quality). Schemas: `ClaimItem`, `GistItem`,
`GistBlock`, `GistBatchOutput`, plus their `Input`/`Output` pairs.

### `debate/`
`Proposer`, `DebateCritic`, `Synthesizer` — the three components of
the multi-agent debate algorithm. Used by `operad.algorithms.debate`.
Schemas: `Proposal`, `Critique`, `DebateContext`, `DebateRecord`,
`DebateTurn`.

### Planned

- `agents/reasoning/debate.py` and `agents/reasoning/verifier.py` —
  pre-wired multi-agent compositions parallel to `react.py`.
  Algorithms exist; the agent-level pre-wirings do not.
- `agents/conversational/TurnTaker`.

## 7. Algorithms — `operad.algorithms`

Orchestrators that take Agents as parameters and close a loop with
metric feedback. Plain classes with `run(...)` — not `Agent` subclasses.

| Algorithm        | Shape                                                      |
| ---------------- | ---------------------------------------------------------- |
| `Beam`           | Generate N candidates; pick top-K by metric.               |
| `Debate`         | Proposer + DebateCritic rounds; Synthesizer final.         |
| `VerifierLoop`   | Generator loops until `Verifier` approves or `max_iter` hits. |
| `Sweep`          | Cartesian grid over dotted-path parameters of a seed agent. Returns a `SweepReport` with one `SweepCell` per grid point. |
| `AutoResearcher` | Planner → Retriever → Reasoner → Critic → Reflector loop, wrapped in best-of-N. Plus `ResearchPlan`, `ResearchInput`, `ResearchContext` types. |

```python
from operad.algorithms import Beam, AutoResearcher
beam = Beam(generator=reasoner, critic=critic, n=5)
best = await beam.run(Question(text="…"))
```

Population-search over agent prompts now lives in
[`operad.optim.EvoGradient`](operad/optim/evo.py) as a first-class
optimizer (rewrites agents from textual gradients within a
`Trainer.fit` loop). The previous `Evolutionary` algorithm has been
absorbed there.

### Planned

- `SelfRefine` — Generator → Reflector → Refiner.
- `TalkerReasoner` — interleaved chat + reasoning.

## 8. Metrics — `operad.metrics`

`Metric` is a protocol: `async def score(predicted, expected) -> float`.

| Metric          | Shape                                                     |
| --------------- | --------------------------------------------------------- |
| `ExactMatch`    | 1.0 if `predicted == expected`, else 0.0.                 |
| `Contains`      | 1.0 if `expected` substring is in `predicted`.            |
| `RegexMatch`    | 1.0 if the pattern matches the predicted field.           |
| `JsonValid`     | 1.0 if predicted parses as the target schema.             |
| `Latency`       | Read `latency_ms` off the envelope (observer-friendly).   |
| `Rouge1`        | ROUGE-1 F1 over text fields.                              |
| `RubricCritic`  | LLM judge: an `Agent[Candidate, Score]` used as a Metric. |
| `CostTracker`   | Aggregator; sums per-run cost across observers.           |

## 9. Benchmark — `operad.benchmark`

Typed dataset + evaluation harness.

```python
from operad.benchmark import Dataset, Entry, evaluate
from operad.metrics import ExactMatch

ds = Dataset([
    Entry(input=Q(text="2+2"), expected_output=A(answer="4")),
    Entry(input=Q(text="capital of France"), expected_output=A(answer="Paris")),
], name="trivia", version="v1")

report = await evaluate(agent, ds, [ExactMatch()])
print(report.summary)       # {"exact_match": 1.0}
print(report.hash_dataset)  # stable content hash
```

`Entry` can carry a per-row metric override; `AggregatedMetric` reduces
a list of per-row scores via `mean`/`median`/`min`/`max`/`sum`.

## 10. Configuration & model backends

`Configuration` describes a single model call: backend, model, host,
key at the top level, and sampling / resilience / io / runtime knobs
in four nested sub-models.

```python
cfg = Configuration(
    backend="openai", model="gpt-4o-mini", api_key="…",
    batch=False,
    sampling=Sampling(temperature=0.7, max_tokens=2048, top_p=None, seed=None),
    resilience=Resilience(timeout=30.0, max_retries=2, backoff_base=0.5),
    io=IOConfig(stream=False, structuredio=True, renderer="xml"),
)
```

### Supported backends

| Backend       | Local? | Extra needed      |
| ------------- | ------ | ----------------- |
| `llamacpp`    | yes    | (built-in)        |
| `lmstudio`    | yes    | (built-in)        |
| `ollama`      | yes    | (built-in)        |
| `huggingface` | yes    | `[huggingface]`   |
| `openai`      | hosted | (built-in)        |
| `anthropic`   | hosted | (built-in)        |
| `bedrock`     | hosted | (built-in)        |
| `gemini`      | hosted | `[gemini]`        |

### Batch mode

`Configuration(backend="openai", batch=True, …)` submits to the
provider's batch endpoint and returns a `BatchHandle`; poll with
`operad.core.models.poll_batch(handle)`. Available for `openai`,
`anthropic`, `bedrock`.

## 11. Rendering — three wire formats

| Renderer   | Output                                             | When to use                                                   |
| ---------- | -------------------------------------------------- | ------------------------------------------------------------- |
| `xml`      | `<role>`, `<task>`, `<rules>`, `<output_schema>`…  | Default; Anthropic-style; portable.                           |
| `markdown` | `# Role`, `# Task`, schema-as-table                | Models that follow Markdown better than tag soup.             |
| `chat`     | `list[{"role","content"}]`                         | Backends with native chat templates (llama.cpp, LMStudio…).   |

Precedence: class-level `renderer: ClassVar[str]` beats
`Configuration.renderer` beats the default (`"xml"`).

## 12. Streaming

```python
cfg = Configuration(…, io=IOConfig(stream=True))
leaf = await MyLeaf(config=cfg).abuild()
async for item in leaf.stream(x):
    if isinstance(item, ChunkEvent):
        print(item.text, end="", flush=True)
    else:
        final: OperadOutput = item
```

`await agent(x)` with `stream=True` still returns a single envelope —
it consumes the stream internally. A `"chunk"` observer event fires
per piece.

## 13. Observers & tracing

Global observer `registry` receives `AgentEvent`s on every invoke.

| Observer                 | Output                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------ |
| `JsonlObserver`          | One NDJSON line per event; `save()` to a file.                                       |
| `RichDashboardObserver`  | Live Rich TUI; needs `[observers]`.                                                  |
| `OtelObserver`           | Real OpenTelemetry spans with all operad hashes as span attributes; needs `[otel]`. The OTel `trace_id` of the root span is derived from `run_id` (`int(run_id, 16)`), so deep-links of the form `{backend}/trace/{run_id}` resolve in any OTLP-receiving backend (e.g. Langfuse). Also emits `gen_ai.*` semantic-convention attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.{prompt,completion,total}_tokens`) for richer rendering in LLM-aware backends. |
| `TraceObserver`          | Accumulate into a `Trace` artefact.                                                  |
| `TrainerProgressObserver`| Rich nested progress bars driven by Trainer lifecycle + DataLoader batch events.     |

```python
import operad.tracing as tracing
with tracing.watch(jsonl="run.jsonl"):   # Rich + NDJSON
    out = await agent(x)
# or set OPERAD_TRACE=/tmp/run.jsonl globally
```

Replay via `uv run operad tail run.jsonl --speed=0`.

### Dashboard panels (`apps/dashboard/`)

`operad-dashboard` renders a run-detail page at `GET /runs/{run_id}`
with four per-run panels wired onto the existing event stream:

| Panel                 | Data source                                                  |
| --------------------- | ------------------------------------------------------------ |
| fitness curve         | `generation` events: best-so-far / mean / spread band        |
| mutation heatmap      | `op_success_counts` + `op_attempt_counts` (per-op × gen)     |
| PromptDrift timeline  | `iteration` events from the `PromptDrift` callback (hash delta + changed param paths) |
| training progress     | `Trainer.fit` lifecycle + `DataLoader` `batch_*` events      |

The dashboard keeps a bounded per-run event buffer (default 1000
envelopes) so these panels can reconstruct historical state when a
page is opened mid-run.

### Self-hosted Langfuse stack

A `docker-compose.yml` at the repo root brings up Langfuse v3 (web,
worker, postgres, clickhouse, redis, minio) alongside both operad
apps. operad's `OtelObserver` ships spans to Langfuse via OTLP/HTTP;
the dashboard renders a "View in Langfuse" deep-link on the
run-detail page. Bootstrap via `LANGFUSE_INIT_*` env vars (admin user,
organization, project, API keys) and seed `OTEL_EXPORTER_OTLP_HEADERS`
with `scripts/langfuse_otel_header.sh`. See
[`apps/README.md`](apps/README.md).

### `Trace` + `trace_diff` + schema-drift replay

```python
from operad.runtime.trace import Trace
trace = Trace.load("run.json", agent=agent)       # warns on schema drift
report = await trace.replay(agent, [ExactMatch()], strict=False)  # re-score
```

`trace_diff(prev, next)` compares two runs step-by-step — prompt,
input, latency, response deltas.

## 14. Retry, concurrency, rate limiting

### Per-endpoint slots

```python
import operad
operad.set_limit(backend="openai", concurrency=4, rpm=500, tpm=90_000)
```

Three orthogonal caps. All three stack per `(backend, host)` key;
`rpm`/`tpm` use a monotonic-clock sliding window. `concurrency` is the
existing semaphore bound.

### Retry / backoff

`Configuration(resilience=Resilience(timeout=..., max_retries=2, backoff_base=0.5))` wraps
the provider call inside `Agent.forward`. Retries are NOT triggered
for contract errors (`BuildError`, `pydantic.ValidationError`) or
cancellation. Each invocation's envelope records
`metadata["retries"]` and `metadata["last_error"]`.

## 15. Tool use — typed `Tool[Args, Result]`

```python
from pydantic import BaseModel
from operad.agents.reasoning.schemas import ToolCall, ToolResult
from operad.agents.reasoning.components.tool_user import Tool, ToolUser

class AddArgs(BaseModel):   a: int; b: int
class AddResult(BaseModel): sum: int

class AddTool:
    name = "add"
    args_schema = AddArgs
    result_schema = AddResult
    async def call(self, args: AddArgs) -> AddResult:
        return AddResult(sum=args.a + args.b)

user = await ToolUser(tools={"add": AddTool()}).abuild()
res = await user(ToolCall[AddArgs](tool_name="add", args=AddArgs(a=1, b=2)))
# res.response: ToolResult[AddResult](ok=True, result=AddResult(sum=3))
```

## 16. Process-pool launcher

For tools / leaves that need OS-level isolation:

```python
from operad.runtime.launchers import SandboxPool
pool = SandboxPool(max_workers=4)
result = await pool.run(expensive_fn, *args)
```

Each call runs in a fresh subprocess; good for long-running tool
execution or untrusted code.

## 17. Cassette-based offline tests

Record real LLM calls once; replay them offline on every CI run.

```bash
OPERAD_CASSETTE=record uv run pytest tests/ -v
uv run pytest tests/                   # replays from the JSONL cassettes
```

A `CassetteMiss` names the drifting hash segment so you know *why*
the replay failed:

```
CassetteMiss: no cassette entry for key 3abc12ef
  hash_model  = f1f2f3f4   (✓ 3 entries match)
  hash_prompt = 9a9b9c9d   (✗ not in cassette)
  hash_input  = 11223344   (✓ 1 entry matches)

Most likely: prompt drift.
```

## 18. YAML + CLI

`operad run|trace|graph|tail` operates on a YAML config naming a
fully-qualified agent class. See the README example.

## 19. Typed in-place mutations — `operad.utils.ops`

Structural edits with a diffable payload, used by `Evolutionary` and
`Sweep`:

```python
from operad.utils.ops import AppendRule, EditTask, SetRole
op = AppendRule(path="reasoner", rule="Be concise.")
op.apply(agent)
```

Every op records an undo function; `AgentDiff` lists applied ops.

## 20. Reproducibility fingerprint

Every `OperadOutput` ships with stable hashes, so two runs with
identical code, inputs, model, and seed hash to the same envelope:

| Hash                   | Covers                                                      |
| ---------------------- | ----------------------------------------------------------- |
| `hash_model`           | backend + model + sampling (ignoring host auth tokens).     |
| `hash_prompt`          | rendered system + user message.                             |
| `hash_input`           | canonical JSON dump of the input.                           |
| `hash_output_schema`   | target Pydantic `output` class definition.                  |
| `hash_config`          | the whole `Configuration` (API key redacted).               |
| `hash_graph`           | the `AgentGraph` topology.                                  |
| `hash_content`         | the agent's declared state (role/task/rules/examples/config). |

Identical fingerprints ⇒ cassette hit, `Trace.replay` match, CI-stable
`Experiment.experiment_id` (once that Wave-3 brief lands).

## 21. Training & optimization

Every mutable field on an Agent is a first-class `Parameter`, and
every `Metric` can lift into a `Loss`. `operad.optim` drives agent
improvement with **textual gradients** — Pydantic critiques produced
by LLM critics rather than floats — while keeping the PyTorch
`Parameter → backward → Optimizer → Trainer` spine intact.

```python
agent.mark_trainable(role=True, task=True, rules=True)
for path, p in agent.named_parameters():
    print(path, type(p).__name__, p.requires_grad)
```

### `Parameter` family

| Class                    | Wraps                                    |
| ------------------------ | ---------------------------------------- |
| `TextParameter`          | `role`, `task` — single-string fields.   |
| `RuleListParameter`      | `rules` — `list[str]`.                   |
| `ExampleListParameter`   | `examples` — `list[Example[In, Out]]`.   |
| `FloatParameter`         | `temperature`, `top_p` — bounded floats. |
| `CategoricalParameter`   | `model`, `backend`, `renderer` — vocab.  |

Each carries an optional `ParameterConstraint` (bounds / vocab /
length) which the optimizer consults before accepting an update — the
textual-gradient analogue of gradient clipping.

`Agent.parameters()` / `named_parameters()` yield handles in
attribute-insertion order. `Agent.trainable_parameters()` is the
`requires_grad=True` subset. `mark_trainable(...)` /
`freeze_parameters(...)` / `unfreeze_parameters(...)` flip the
`requires_grad` bit; each takes boolean flags (`role=True`,
`rules=True`, ...) plus `**per_path` kwargs for descendant targeting
(`**{"stage_0.role": True}`).

### Losses

| Class / protocol      | Shape                                                            |
| --------------------- | ---------------------------------------------------------------- |
| `Loss` (protocol)     | `compute(pred, expected) -> (score, TextualGradient)`.           |
| `LossFromMetric`      | Lift any `Metric`; the gradient's `message` is auto-generated.   |
| `CriticLoss(critic)`  | Wrap an `Agent[Candidate, Score]`; rationale ⇒ gradient.         |
| `JSONShapeLoss`       | 0.0 if `pred` matches the expected Pydantic shape, 1.0 otherwise.|
| `CompositeLoss`       | Weighted sum of child losses; merges each child's gradient.      |

### Tape + `backward()`

`operad.optim.tape()` is an async context manager that installs a
`TapeObserver` on the observer registry; every `Agent.invoke` inside
the context records a `TapeEntry`. `backward()` walks the tape in
reverse, propagating a `TextualGradient` through each node via the
registered `BackpropAgent`s and populating `Parameter.grad`.

```python
async with operad.optim.tape() as t:
    out = await agent(x)
score, grad = await loss_fn.compute(out.response, y)
await t.backward(grad, parameters=list(agent.parameters()))
```

### Hooks + `no_grad()`

```python
handle = agent.register_forward_hook(lambda a, x, y: print(a.name, y))
# handle.remove() detaches it.
```

`register_forward_pre_hook`, `register_forward_hook`,
`register_backward_hook` all return a `Handle` with `.remove()`. An
`async with operad.no_grad():` block disables tape recording for
inference-speed runs. `operad.inference_mode()` is the same thing
with hooks also suppressed.

### Optimizer fleet

| Class                      | Shape                                                                    |
| -------------------------- | ------------------------------------------------------------------------ |
| `TextualGradientDescent`   | Naive per-parameter rewrite from the current `grad`.                     |
| `MomentumTextGrad`         | Maintains a running text summary across steps via `GradSummarizer`.      |
| `EvoGradient`              | Mutation-selection over a population; best survivor wins the step.       |
| `OPROOptimizer`            | LLM-as-optimizer with a history window of (prompt, score) pairs.         |
| `APEOptimizer`             | Candidate generator + ranker; samples many rewrites, keeps the best.     |

Every optimizer takes a `list[Parameter] | list[ParamGroup]` with
per-group `lr`, `momentum`, and constraint overrides. `zero_grad()`
clears grads; `await step()` applies them. `state_dict()` /
`load_state_dict()` are live on `Optimizer` and `LRScheduler` for
checkpointing.

### LR schedulers

| Class                | When to use                                                      |
| -------------------- | ---------------------------------------------------------------- |
| `ConstantLR`         | Baseline; no annealing.                                          |
| `StepLR`             | Drop lr by `gamma` every `step_size` epochs.                     |
| `MultiStepLR`        | Drop lr at explicit epoch milestones.                            |
| `ExponentialLR`      | Multiplicative decay `lr *= gamma` each epoch.                   |
| `CosineExplorationLR`| Cosine anneal from `base_lr` to `eta_min` over `T_max` epochs.   |
| `WarmupLR`           | Linear ramp-up over the first `warmup_epochs`.                   |
| `ReduceLROnPlateau`  | Watches a validation metric; drops lr when it stalls.            |
| `ChainedScheduler`   | Compose several schedulers that all step every epoch.            |
| `SequentialLR`       | Hand off between schedulers at configured milestones.            |

In operad, `lr` is the aggression knob the `RewriteAgent` reads: low
`lr` nudges a parameter's value, high `lr` rewrites it.

### `Trainer`

```python
trainer = Trainer(
    agent, optimizer, loss_fn,
    scheduler=scheduler,
    callbacks=[EarlyStopping(...), BestCheckpoint(...)],
    metrics=[ExactMatch()],
    max_grad_norm=None,
    accumulation_steps=1,
)
report = await trainer.fit(loader, val_ds=val, epochs=5)
await trainer.evaluate(test_ds)          # -> EvalReport
out = await trainer.predict(x)            # -> OperadOutput[Out]
```

Each sample opens its own `tape()`, computes the loss, and calls
`backward()`. Per-sample gradients merge onto `Parameter.grad`
(messages joined with `\n---\n`, `target_paths` unioned, `severity`
= max). `optimizer.step()` fires every `accumulation_steps` batches,
with a residual flush at epoch end.

| Callback                | Effect                                                            |
| ----------------------- | ----------------------------------------------------------------- |
| `EarlyStopping`         | Halts when a monitored metric stops improving.                    |
| `BestCheckpoint`        | Snapshots the agent's `hash_content` at the best epoch.           |
| `GradClip`              | Clamps `TextualGradient.severity` per step.                       |
| `PromptDrift`           | Per-epoch hash diff; also emits `AlgorithmEvent` rows for the dashboard's drift timeline. |
| `LearningRateLogger`    | Records each group's lr at every epoch boundary.                  |
| `MemoryRotation`        | Guards tape growth on long runs by rotating old entries.          |
| `HumanFeedbackCallback` | Appends per-validation `(input, predicted)` rows to an NDJSON file for human rating. |

### Human-in-the-loop training (Studio app)

`HumanFeedbackCallback` + `HumanFeedbackLoss` close the labeling
loop. The callback writes one NDJSON row per validation sample;
`apps/studio/` is a FastAPI app that lets a single human assign
1-5 ratings via the browser and relaunch `Trainer.fit` with
`HumanFeedbackLoss(ratings_path)` from a saved bundle.

```bash
uv run operad-studio --port 7870 \
  --data-dir /tmp/operad-feedback \
  --agent-bundle /tmp/talker.json \
  --dashboard-port 7860
```

Training events from the background `Trainer.fit` task forward to
the running dashboard via `operad.dashboard.attach`, so both UIs
update in sync.

### Data

```python
from operad.data import DataLoader, random_split
train, val = random_split(dataset, [0.8, 0.2], seed=0)
loader = DataLoader(train, batch_size=8, shuffle=True)
```

Samplers: `RandomSampler`, `SequentialSampler`,
`WeightedRandomSampler`. Batches arrive as
`Batch[In, Out](inputs, expected)`.

### `state_dict` / `load_state_dict`

Live on `Optimizer` and `LRScheduler` today (step counts, momentum
summaries, epoch state). On `Agent`, `state_dict()` / `load_state_dict()`
are PyTorch-style aliases for `state()` / `load_state()` — both pairs
are equally first-class.

## 22. PromptTraceback

`PromptTraceback` is the optim-layer counterpart to a Python
traceback: given a `Tape` and a `path -> TextualGradient` map, it
renders each recorded node in reverse call order so a user can debug
a bad training batch the same way they debug a bad call.

```python
from operad.optim import tape, traceback as ptb
async with tape() as t:
    out = await agent(x)
score, loss = await loss_fn.compute(out.response, expected)
tb = ptb.PromptTraceback.from_run(t, loss)
print(str(tb))                 # plain-text stanzas
print(tb.to_markdown())        # PR-body friendly
tb.save("traceback.ndjson")    # NDJSON, one frame per line
```

Lives in [`operad/optim/traceback.py`](operad/optim/traceback.py) —
exports `PromptTraceback`, `TracebackFrame`, and `traceback`.

### Planned

- **Cassette-replay determinism validation** — full validation
  matrix for offline-deterministic training under
  `OPERAD_CASSETTE=record/replay`.
