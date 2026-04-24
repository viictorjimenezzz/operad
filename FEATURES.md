# operad — Feature catalog

A concise enumeration of what the library provides, how the pieces fit
together, and the one-liner you need to use each one. For design
rationale, see [VISION.md](VISION.md); for the README-level intro, see
[README.md](README.md).

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
| `state()` / `load_state(…)`  | Snapshot / restore declared attributes.                                       |
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
`Reasoner`, `Actor`, `Classifier`, `Critic`, `Evaluator`, `Extractor`,
`Planner`, `Reflector`, `Retriever`, `Router`, `ToolUser`; plus `ReAct`
composition.

### `coding/`
`CodeReviewer`, `DiffSummarizer`, `ContextOptimizer`, and `PRReviewer`
top-level composite.

### `conversational/`
`Persona`, `Safeguard`, `TurnTaker`, `RefusalLeaf`, and `Talker`
(end-to-end safeguarded chat pipeline).

### `memory/`
`BeliefExtractor`, `EpisodicSummarizer`, `UserModelExtractor`.

### `safeguard/`
Task-agnostic guardrails: `InputSanitizer[T]` (redact / truncate /
lowercase before forward) and `OutputModerator[T]` (classify any
payload). Compose via `Pipeline` or `forward_in`/`forward_out` hooks:

```python
from operad.agents.safeguard import InputSanitizer, OutputModerator
safe_pipeline = Pipeline(
    InputSanitizer(schema=Question),
    Reasoner(config=cfg, input=Question, output=Answer),
    OutputModerator(schema=Answer, config=cfg),
)
```

## 7. Algorithms — `operad.algorithms`

Orchestrators that take Agents as parameters and close a loop with
metric feedback. Plain classes with `run(...)` — not `Agent` subclasses.

| Algorithm        | Shape                                                      |
| ---------------- | ---------------------------------------------------------- |
| `BestOfN`        | Generate N candidates; pick highest-scored under a Metric. |
| `Debate`         | Proposer + Critique rounds; converges on a winning `Proposal`. |
| `SelfRefine`     | Generator → Reflector → Refiner loop until satisfied.      |
| `VerifierLoop`   | Actor loops until `Verifier` approves or `max_iter` hits.  |
| `Evolutionary`   | Population of agent variants; mutate + select on metric.   |
| `Sweep`          | Cartesian grid over dotted-path parameters of a seed agent.|
| `AutoResearcher` | Planner → Retriever → Reasoner → Critic → Reflector loop, wrapped in `BestOfN`. |

```python
from operad.algorithms import BestOfN, AutoResearcher
bon = BestOfN(generator=reasoner, critic=critic, n=5)
best = await bon.run(Question(text="…"))
```

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
key, and all sampling / resilience / rendering knobs in one flat
object.

```python
cfg = Configuration(
    backend="openai", model="gpt-4o-mini", api_key="…",
    temperature=0.7, max_tokens=2048, top_p=None, seed=None,
    timeout=30.0, max_retries=2, backoff_base=0.5,
    stream=False, structuredio=True, renderer="xml",
    batch=False,
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
cfg = Configuration(…, stream=True)
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

| Observer               | Output                                                |
| ---------------------- | ----------------------------------------------------- |
| `JsonlObserver`        | One NDJSON line per event; `save()` to a file.        |
| `RichDashboardObserver`| Live Rich TUI; needs `[observers]`.                   |
| `OtelObserver`         | Real OpenTelemetry spans with all operad hashes as span attributes; needs `[otel]`. |
| `TraceObserver`        | Accumulate into a `Trace` artefact.                   |

```python
import operad.tracing as tracing
with tracing.watch(jsonl="run.jsonl"):   # Rich + NDJSON
    out = await agent(x)
# or set OPERAD_TRACE=/tmp/run.jsonl globally
```

Replay via `uv run operad tail run.jsonl --speed=0`.

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

`Configuration(timeout=..., max_retries=2, backoff_base=0.5)` wraps
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
