# operad — vision and direction

This document is the north star for the `operad` library: the bet we
are making, the mental model we borrow from, and the kind of system we
expect to have in twelve months. It is required reading for anyone
contributing code, whether human or agent.

## 1. Vision in one sentence

**operad is the `torch.nn` of local-first agent systems: typed,
composable agent modules; algorithms that compose those modules into
coordinated behavior; and metrics that can feed results back into the
loop.**

The library is built on top of [Strands Agents](https://strandsagents.com/)
and is designed around locally-served OpenAI-compatible model servers
(LMStudio, `llama-server`, Ollama), but nothing in the foundations
prevents it from pointing at hosted providers.

## 2. The name

An **operad** is the mathematical structure of abstract operations that
compose by trees. An element of an operad is an `n`-ary operation with
a fixed output; composition plugs the output of one operation into one
of the inputs of another, producing a new, deeper operation. The
collection of all such compositions obeys associativity and the obvious
equivariance under relabeling.

Every `Agent[In, Out]` in this library is a typed operation. `Pipeline`
composes them sequentially; `Parallel` fans them out and joins the
results through an `n`-ary combine step; a future `Debate` would
introduce mutual critique before a synthesis node. `build()` captures
the tree of operations symbolically, checks every edge for type
compatibility, and freezes it into an `AgentGraph` — a first-class
value you can export, mutate, or run.

The name is literal, not decorative: this library *is* a library of
typed operations that compose by trees, with a build step that makes
the composition explicit.

## 3. The big bet

Most agent frameworks today land in one of two camps:

- **Graph DSLs** (LangGraph, state machines): nodes and edges are a
  separate language from the code that runs inside them. Type safety
  stops at the node boundary; you edit YAML to change composition.
- **Role-play systems** (AutoGen, CrewAI): agents are named personas
  that converse; composition is a conversation, which is neither typed
  nor reproducible.

`operad` bets on a third path: **agents are Python modules in the
`torch.nn` sense**. They have typed inputs and outputs, they can be
nested, they can be serialized, they can be mutated in place, and
their composition is *itself* a module. If that bet pays off, three
things become possible:

1. The same surface expresses one-shot leaves, fan-outs, pipelines,
   best-of-N, debates, evolutionary loops, and self-improvement — with
   no new primitives.
2. Dashboards, observability, cost estimation, and optimization all
   hang off a single computation graph captured before any token is
   generated.
3. Prompts, temperatures, and topologies are parameters that can be
   swept over, A/B-tested, and mutated by other agents — because
   they're just Pydantic objects, not YAML.

Everything else in this document is in service of that bet.

## 4. The PyTorch analogy

The mental model deliberately mirrors `torch.nn` at every level.

| PyTorch                          | operad                                                       |
| -------------------------------- | ------------------------------------------------------------ |
| `nn.Module`                      | `Agent` (single class; leaves and composites)                |
| module weights / params          | agent state (config, role, task, rules, examples, I/O types) |
| `forward(x)`                     | `forward(x: In) -> Out` (async)                              |
| `Module.__call__`                | `Agent.__call__` / `invoke` (validates contract)             |
| child module tracking            | `__setattr__` hook registers sub-`Agent`s                    |
| `torch.compile` / `fx`           | `build()` with symbolic tracing                              |
| `torch.fx.Graph`                 | `AgentGraph` of `Edge` + `Node` objects                      |
| `torch.nn` library               | `agents/` (typed, composable Agent subclasses)               |
| `torchmetrics`                   | `metrics/` (deterministic scorers)                           |
| `nn.Parameter`                   | `operad.optim.Parameter`                                     |
| `loss.backward()`                | `await tape.backward(loss)` (walks the runtime tape)         |
| `torch.optim.*`                  | `operad.optim.*` (SGD / Momentum / Evo / OPRO / APE)         |
| `torch.optim.lr_scheduler.*`     | `operad.optim.lr_scheduler.*`                                |
| `torch.utils.data.DataLoader`    | `operad.data.DataLoader`                                     |
| `lightning.Trainer`              | `operad.train.Trainer`                                       |
| `torch.no_grad()`                | `async with operad.no_grad():`                               |
| `Module.register_forward_hook`   | `Agent.register_forward_hook`                                |
| numerical-loop algorithms        | `algorithms/` (non-Agent loops: BestOfN, Evolutionary, …)    |

Two consequences follow from taking this analogy seriously:

1. **A component is an `Agent` subclass** — leaves, pipelines,
   parallel fan-outs, and the leaf starter pack (`Reasoner`,
   `Extractor`, `Classifier`, `Planner`, `Critic`, ...) all satisfy
   the typed `Agent[In, Out]` surface and nest freely.
2. **Algorithms are *not* Agents.** An `Evolutionary[Template, Agent]`
   that mutates prompts, evaluates populations, selects survivors,
   and iterates has a shape that doesn't fit `x: In -> y: Out`.
   Forcing every outer loop into the Agent mold loses information and
   produces awkward constructors. Algorithms are plain classes with
   whatever `run(...)` signature they need; they take Agents as
   parameters and operate on their outputs with metric feedback.

## 5. The three core abstractions

### 5.1 `Agent[In, Out]`

- Inherits from `strands.Agent`.
- Generic over its input and output Pydantic classes, so composition is
  type-checkable in your IDE.
- Holds all its "hyperparameters" directly on the instance — no wrapper
  object. The full surface is: `config`, `role`, `task`, `rules`,
  `examples`, `input`, `output`. Class-level attribute defaults carry
  the opinionated values for each component; the constructor merges
  them with any per-instance overrides.
- Leaves: use the default `forward`, which delegates to
  `strands.Agent.invoke_async(..., structured_output_model=...)` to get
  validated structured output.
- Composites: override `forward` to route between child `Agent`s.
  Children assigned as attributes are auto-registered (PyTorch
  `__setattr__` trick).
- `strands.Agent.__init__` is intentionally deferred to `build()` so
  that constructing an `Agent` has zero network/provider side effects.

### 5.2 Agent "hyperparameters" (role / task / rules / examples)

The four structural prompt sections live on the Agent itself. The
field set comes from cross-referencing DSPy Signatures, the TELeR
taxonomy, PICCO, and the Prompt Report (Schulhoff et al. 2024) —
what's common to all of them is here; the rest is either redundant
with our typed I/O schemas or better pushed into `In`:

- `config: Configuration | None` — backend + sampling knobs; `None`
  for pure-router composites.
- `role: str` — the persona the agent adopts.
- `task: str` — the single most important instruction.
- `rules: list[str]` — hard constraints.
- `examples: list[Example[In, Out]]` — *typed* few-shot pairs
  (DSPy-style: each demonstration is a full `(In, Out)` instance, not
  a string).
- `input: type[In]` / `output: type[Out]` — the typed contract.

The default renderer surfaces section descriptions (persona, task,
etc.) as XML `desc="..."` attributes so the model is told what each
section *means*, not just what it says. The same trick surfaces
`Field(description=...)` on the user's own `In` and `Out` schemas,
which is the DSPy insight that per-field semantics belong in the
prompt contract.

Because every knob is a plain mutable attribute, evolutionary search,
hyperparameter sweeps, A/B prompt comparison, and runtime prompt
swapping are all *just mutations* — no special framework support
needed.

Components declare opinionated defaults at the class level:

```python
class Reasoner(Agent[In, Out]):
    role = "You are a careful, methodical reasoner."
    task = "Work through the problem step-by-step, then commit to an answer."
    rules = ("Show your reasoning before the final answer.", ...)
```

Instantiation is `Reasoner(config=cfg, input=Q, output=A)` (or a
subclass that pins `input`/`output` at the class level). Any field
can be overridden at construction time or mutated on the instance
(`leaf.task = "..."`) afterwards.

### 5.3 `build()` — the "compile" step

`agent.build()` (sync) or `await agent.abuild()` (inside a running
loop) prepares a composed architecture for repeated `invoke()` calls.
It:

1. **Validates** every agent in the tree (input/output types set;
   leaves have a config).
2. **Resolves models**: `Configuration` → `strands.models.Model` via
   `operad.models.resolve_model`, wiring leaves that use the default
   `forward`.
3. **Symbolically traces**: `forward()` is called once with a sentinel
   input. Child `invoke` calls are intercepted by a `Tracer` installed
   via an `asyncio.ContextVar`.
   - Each edge is type-checked (caller input vs child's `input`).
   - Each edge is recorded as
     `Edge(caller, callee, input_type, output_type)`.
   - Composites recurse; leaves return a typed `model_construct()`
     output.
   - No LLM is contacted.
4. **Checks root output** against the root's `output`.
5. **Freezes**: stores `AgentGraph` on `root._graph`, flips `_built`
   on every node in the tree.

The payoff: architecture errors (mismatched types, missing contracts,
wrong return types) are caught *before any token is generated*, and
you get a free computation graph for observability
(`operad.to_mermaid`, `to_json`).

**Important constraint** (shared with `torch.fx`): `forward()` is
called with sentinel inputs during tracing, so composite `forward`
methods must *route* rather than *branch on payload values*. Pydantic
field defaults land in the sentinel; if your logic needs a real value,
do it inside a leaf. The build-time proxy planned for iteration 4
will turn this silent footgun into a hard error.

## 6. Where we are today

The full `torch.nn` + `torch.fx` + `torch.optim` + `torch.utils.data`
+ `pytorch-lightning` surface area, in operad terms.

```
operad/
  core/
    agent.py        Agent[In, Out] with class-attribute defaults; Example;
                    parameters() / named_parameters() / mark_trainable();
                    register_forward_hook / pre-hook / backward hook
    config.py       Configuration, Backend
    build.py        Tracer, AgentGraph, Edge, Node, build_agent, abuild_agent
    graph.py        to_mermaid, to_json exporters
    render.py       XML-tagged description-aware prompt renderer
  utils/errors.py   BuildError + BuildReason
  models/           resolve_model dispatcher, one file per backend
  runtime/slots.py  SlotRegistry, acquire, set_limit
  agents/           organized by domain: each <domain>/ has its own
                    components/ subfolder + composed patterns at root
    pipeline.py     structural operators (domain-agnostic)
    parallel.py
    reasoning/
      components/   Reasoner, Actor, Extractor, Evaluator,
                    Classifier, Planner, Critic (leaf Agent subclasses)
      react.py      Reason-Act-Observe-Evaluate composition
  algorithms/       BestOfN, Debate, SelfRefine, VerifierLoop,
                    Evolutionary, Sweep, AutoResearcher
  metrics/          Metric protocol, ExactMatch / JsonValid / Latency / …
  optim/            Parameter, TextualGradient, tape / backward,
                    Loss + CriticLoss + LossFromMetric + CompositeLoss,
                    Optimizer base + TextualGradientDescent +
                    MomentumTextGrad + EvoGradient + OPROOptimizer +
                    APEOptimizer; LR scheduler family;
                    BackpropAgent, RewriteAgent
  train/            Trainer (fit / evaluate / predict) + callbacks
                    (EarlyStopping, BestCheckpoint, GradClip,
                    PromptDrift, LearningRateLogger, MemoryRotation);
                    EpochReport, TrainingReport
  data/             DataLoader, Batch, Sampler family, random_split
tests/              offline by default; `tests/integration/` opt-in via
                    OPERAD_INTEGRATION env var
examples/           parallel.py — fan-out reasoners over a shared prompt
```

Iteration 4 delivers the optim/train layer on top of the existing
foundations: typed `Parameter` handles, textual-gradient propagation
via a runtime tape, the full optimizer fleet, LR schedulers, and a
PyTorch-Lightning-style `Trainer`. The wave-by-wave plan lives in
[`.conductor/optim/`](.conductor/optim/).

New domains slot in as sibling folders of `reasoning/`:

* `coding/` — code-review components, PR synthesizers
* `conversational/` — turn-taking, safeguards, persona management
* `memory/` — belief / user-fact extractors, retrieval helpers
* `<your-domain>/` — same shape

Every composed pattern is free to import components from sibling
domains (`ReAct`'s `Reasoner` already does).

Iterations 1–3 deliver: real end-to-end execution against llama.cpp /
LM Studio / Ollama / OpenAI / Bedrock; honest `Configuration`
threading; per-endpoint concurrency slots; DSPy-grounded structured
prompts living directly on the Agent (no wrapper object) with typed
few-shot examples and description-aware rendering; the first seven
leaf components; a pre-wired ReAct composition; the
components-vs-algorithms taxonomy; a minimal metrics package; and
graph export.

## 7. Where we're going

Layers planned for upcoming iterations. Each slots onto the
foundations without revisiting them.

```
operad/
  core/
    render.py           additional renderers (Markdown, chat-template-aware)
    build.py            sentinel proxy: detect payload-branching in composites
                        at trace time, turning today's silent footgun into a
                        BuildError with a pointer at the offending if/for
  runtime/
    observers/          hook protocol on `Agent.invoke`, Rich TUI dashboard,
                        JSONL log writer, OpenTelemetry bridge
    launchers/          asyncio (default) / process / macOS Terminal
  agents/
    reasoning/
      components/       ToolUser, Retriever, Reflector, Router-by-enum
      debate.py         more pre-wired patterns alongside react.py
      verifier.py
    coding/
      components/       context_optimizer, reviewer
      pr_reviewer.py
    conversational/
      components/       safeguard, turn-taker
      talker.py
    memory/
      components/       beliefs, user_model, episodic
  algorithms/           Debate, VerifierLoop, SelfRefine, TalkerReasoner,
                        Evolutionary, AutoResearch
  metrics/              rubric-driven judges, cost/token accounting
  configs/              YAML/JSON entrypoints that instantiate algorithms
  cli.py                `operad run config.yaml`
```

Iteration 4 focuses on correctness + observability: the sentinel
proxy closes the "composite branches on payload" footgun, and the
observer protocol gives us a single hook point for a Rich dashboard,
JSONL logging, cost accounting, and the eventual HTML report.

One north-star milestone remains explicitly on the roadmap:

1. **`AutoResearcher` on 8 concurrent llama-server slots**: plan →
   retrieve → read → write → verify → reflect, all local, all
   observable in a live dashboard, with per-agent metrics feeding an
   outer best-of-N loop.

The original north star — **`Evolutionary` as a non-Agent algorithm
whose output is an improved Agent** — is now **SHIPPED**. The
optim/train layer (`Parameter`, `backward()`, `Optimizer`, `Trainer`)
landed in commits `368bd8a..126434b`; `EvoGradient` is a first-class
`Optimizer` subclass that rewrites agents from textual gradients, and
`Agent.auto_tune` wraps `Evolutionary` as the one-liner entry point.
See [`.conductor/optim/`](.conductor/optim/) for the task plan and
[`apps/demos/agent_evolution/run.py`](apps/demos/agent_evolution/run.py)
for a live, fully-offline demo.

A second milestone — **training observability and human-in-the-loop
labeling** — is also now **SHIPPED**. Four per-run dashboard panels
(fitness curve, mutation heatmap, `PromptDrift` timeline, training
progress) render live at `GET /runs/{run_id}` on
`apps/dashboard/`, driven entirely by the existing observer
registry. A sibling **Studio** app (`apps/studio/`) closes the loop:
`HumanFeedbackCallback` writes `(input, predicted)` rows during
`Trainer.fit`, a human assigns 1-5 ratings in the UI, and the same
ratings file is replayed as a `HumanFeedbackLoss` on the next fit.
See [`.conductor/training-v2/`](.conductor/training-v2/) for the
task plan.

## 8. Non-goals and deliberate omissions

- **No static-type-checker runtime integration** (`ty`, `mypy`, etc.).
  The library is fully typed (PEP 561 via `py.typed`) so your IDE/CI
  gets full IntelliSense. `build()` handles dynamic validation. We do
  not shell out to external type checkers.
- **No prompt templating engine** in the foundations. Prompt sections
  (`role`, `task`, `rules`) are plain strings, rendered by the
  built-in XML renderer. If Jinja/format-style templating is needed
  later, it will slot in by overriding `Agent.format_system_message`
  — the foundation doesn't change.
- **No agent DSL, YAML/JSON schema, or blueprint system** in the
  foundations. Configurations arrive later in `configs/`.
- **No hidden model-provider fallbacks.** `Configuration.backend` is
  the single source of truth. Provider resolution happens explicitly
  in `operad.models`.

## 9. Contributor checklist

When adding to the library:

1. **Preserve the components-vs-algorithms split.** If a new
   abstraction has a typed `In -> Out` contract, it's a component and
   subclasses `Agent[In, Out]`. If it orchestrates agents with a loop
   + metric feedback and its natural API isn't `__call__(x)`, it's an
   algorithm and lives as a plain class with a `run(...)` method.
2. **Declare component contracts as class attributes.** `input`,
   `output`, `role`, `task`, `rules`, `examples` all live on the
   class body. Construction kwargs override them.
3. **Write composite `forward` as a router, not a calculator.**
   Inspect payload values only inside leaves or post-invoke;
   composites just orchestrate child calls. (Iteration 4's sentinel
   proxy will catch violations at build time.)
4. **Keep `__init__` free of side effects.** No network, no provider
   handshakes, no model loading. All of that belongs in `build()`.
5. **Add offline tests.** Use `FakeLeaf`-style helpers — anything
   that overrides `forward` skips strands wiring and runs in the test
   process without network.
6. **Extend, don't fork, the public API.** New abstractions slot into
   `agents/`, `algorithms/`, `metrics/`, or `runtime/`; the
   foundations under `core/` and `utils/errors.py` should rarely
   change.

## 10. Training as the next frontier

The library now contains both inference and training. `operad.optim`
is our TextGrad / OPRO / APE analogue: textual gradients are
LLM-generated natural-language critique instead of floats, but the
spine — `Parameter → backward → Optimizer → Trainer` — is the same
one that `torch.optim` exposes. The gradient agents (`BackpropAgent`)
and the rewrite agents (`RewriteAgent`) are themselves `Agent`
subclasses, so the whole observer / cassette / hashing stack composes
straight through a fit loop.

The open research surface here is **meta-optimization**: an optimizer
is an agent, which means its own `role`, `task`, `rules`, and
sampling are `Parameter`s. A `Trainer` optimizing the
`OPROOptimizer` that optimizes a `Pipeline` is the same three-level
stack that PyTorch gets with learned optimizers — except the gradient
language is English, not a tensor.

Further reading: [TRAINING.md](TRAINING.md),
[`operad/optim/README.md`](operad/optim/README.md),
[`.conductor/optim/0-0-orchestration.md`](.conductor/optim/0-0-orchestration.md),
and [`apps/demos/agent_evolution/run.py`](apps/demos/agent_evolution/run.py)
(the flagship offline agents-optimizing-agents demo).
