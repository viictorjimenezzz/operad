# operad — the library

This file is the bridge between [`VISION.md`](../VISION.md) (purpose,
roadmap) and the per-submodule READMEs under each `operad/<module>/`.
Read this once to internalize the mental model; jump to a submodule
README for files, public API, and extension points.

---

## The mental model

Four idioms a contributor must internalize before adding code:

1. **Typed `Agent[In, Out]`.** Every unit of work is a typed,
   composable agent. Leaves declare their contract on the class body
   (`input`, `output`, `role`, `task`, `rules`, `examples`); composites
   override `forward` to route between children.

2. **`build()` is the compile step.** It walks the tree, type-checks
   every parent-to-child handoff, resolves model backends, and freezes
   the result into an `AgentGraph`. No model is contacted. The graph
   is a first-class data structure you can hash, export, replay, or
   feed to `backward()`.

3. **Composition is by tree.** `Pipeline` (sequential), `Parallel`
   (fan-out + combine), `Switch` (runtime routing), `Router` (typed
   choice). Composites assigned as `__setattr__` children are
   auto-registered, in PyTorch `nn.Module` style.

4. **Trainability via `Parameter` handles.** Every mutable field on an
   agent (`role`, `task`, `rules`, `examples`, sampling, model,
   backend) is a `Parameter`. `agent.parameters()` /
   `named_parameters()` / `mark_trainable()` give you handles you can
   sweep, A/B, or train against textual gradients.

These four idioms recur in every submodule. The whole library is
machinery that makes them work together.

## How the submodules compose

```
        ┌──────────── runtime/ (cross-cuts everything: observers, slots, traces, retry, cost) ────────────┐
        │                                                                                                 │
        │   ┌─────────────────────────  inference path ─────────────────────────┐                         │
        │   │  core/  ──►  agents/  ──►  algorithms/                            │                         │
        │   │     │                                                             │                         │
configs/│   │     │     ┌───────────  improvement path  ───────────┐            │                         │
   +    │   │     ▼     ▼                                          │            │                         │
 cli.py │   │  metrics/, benchmark/, data/, optim/   ──►    train/ │            │                         │
        │   └────────────────────────────────────────────────────────────────────┘                         │
        └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- The **inference path** (`core` → `agents` → `algorithms`) is what
  runs your workflow.
- The **improvement path** (`metrics` + `benchmark` + `data` + `optim`
  + `train`) is what makes the workflow trainable.
- `runtime/` cross-cuts both — every event during inference *and*
  training flows through the same observer registry.
- `configs/` + `cli.py` are the YAML/CLI entrypoints; `tracing.py` is
  the one-liner observer entrypoint.

## Per-submodule rationale

### `core/` — the foundation

`Agent`, `Pipeline`, `Parallel`, `build`, `AgentGraph`, `Configuration`,
`Example`, `OperadOutput`, `freeze`/`thaw`, model backend dispatch,
state diffing. The shape of every other submodule is constrained by
what `core` exposes: an `Agent` is the unit, the `AgentGraph` is the
substrate, the `Configuration` is the call descriptor, the
`OperadOutput` envelope is the reproducibility contract. **Read first.**
→ [`core/README.md`](core/README.md).

### `utils/` — cross-cutting helpers

`BuildError` + reasons, the `hash_*` family for content-addressable
identity, `Op`/`CompoundOp` mutation primitives consumed by
`EvoGradient` and `RewriteAgent`, cassette record/replay, path
resolution. Tiny but load-bearing — a new trainable parameter type
typically lands here as a new `Op`.
→ [`utils/README.md`](utils/README.md).

### `runtime/` — execution + observability spine

Concurrency slots (per-endpoint caps + RPM/TPM windows), traces and
trace-diffs, the observer registry (Rich TUI, JSONL, OpenTelemetry,
web-dashboard), cost accounting, retry policies, streaming chunk
events, sandboxed launcher pool. Everything that fires during a run
flows through this layer; this is what makes inference *and* training
observable on the same plumbing.
→ [`runtime/README.md`](runtime/README.md).

### `agents/` — the component library

The `torch.nn`-style tier: domain-organized leaves + structural
operators. One folder per domain (`reasoning/`, `coding/`,
`conversational/`, `memory/`, `retrieval/`, `safeguard/`, `debate/`),
each with a `components/` subdir for leaves and a domain-root file
for any pre-wired composite (e.g. `reasoning/react.py`). Adding a new
domain is a sibling folder mirroring this layout.
→ [`agents/README.md`](agents/README.md).

### `algorithms/` — outer loops

`Beam`, `Debate`, `Sweep`, `VerifierLoop`, `AutoResearcher`. Plain
classes whose `run(...)` orchestrates `Agent`s with metric feedback.
**Not** `Agent` subclasses — their natural API is not `__call__(x)`.
This is where "agents improving agents" lives at the algorithmic
layer; the same idea formalized into a fit loop lives in `optim/` +
`train/`.
→ [`algorithms/README.md`](algorithms/README.md).

### `metrics/` — pluggable scorers

Deterministic (`ExactMatch`, `Contains`, `RegexMatch`, `JsonValid`,
`Rouge1`, `Latency`) and LLM-driven (`RubricCritic` wraps an
`Agent[Candidate, Score]` so the judge's rationale becomes both score
and gradient text). `CostTracker` aggregates token+dollar cost across
runs.
→ [`metrics/README.md`](metrics/README.md).

### `benchmark/` — typed evaluation

`Dataset[Example]`, `Entry`, `evaluate(agent, ds, metrics) ->
EvalReport`, `Experiment`, `SensitivityReport`, `RegressionReport`.
Datasets are first-class, metrics are composable, and the harness
detects regressions across versions and prompt-perturbation
sensitivity in one pass.
→ [`benchmark/README.md`](benchmark/README.md).

### `data/` — iteration + sampling

`DataLoader`, `Batch`, sampler family (`SequentialSampler`,
`RandomSampler`, `WeightedRandomSampler`, `UncertaintySampler`),
`random_split`. Mirrors `torch.utils.data` ergonomically; the active
learning hook is the `UncertaintySampler` that biases batches toward
high-uncertainty examples.
→ [`data/README.md`](data/README.md).

### `optim/` — textual-gradient training stack

`Parameter` handles, `TextualGradient` (Pydantic critique),
`tape()`/`backward()` runtime tape walker, the `Optimizer` fleet
(`TextualGradientDescent`, `MomentumTextGrad`, `EvoGradient`,
`OPROOptimizer`, `APEOptimizer`), LR schedulers, `BackpropAgent`,
`RewriteAgent`. The whole training spine; gradients are LLM critiques,
not floats.
→ [`optim/README.md`](optim/README.md).

### `train/` — the fit loop

`Trainer.fit/evaluate/predict`, callbacks (`EarlyStopping`,
`BestCheckpoint`, `GradClip`, `PromptDrift`, `LearningRateLogger`,
`MemoryRotation`, `HumanFeedbackCallback`), `HumanFeedbackLoss`,
`EpochReport`/`TrainingReport`, `TrainerProgressObserver`. The
PyTorch-Lightning analog — one entry point glues optimizer + loss +
scheduler + metrics + callbacks.
→ [`train/README.md`](train/README.md).

### `configs/` — YAML loader

`load(path) -> RunConfig`, `instantiate()`, `apply_runtime()` plus the
Pydantic schemas. A thin deserializer over the Python API, not a
separate language. Drives `operad run`.
→ [`configs/README.md`](configs/README.md).

### `cli.py`, `tracing.py`, `dashboard.py`

Top-level entrypoints. `cli.py` exposes `operad run/trace/graph/tail`.
`tracing.py` is the `watch()` context manager + `OPERAD_TRACE` env
auto-registration. `dashboard.py` is a tiny POST helper that forwards
events to a running `apps/dashboard/` server.

## How to extend

| What you want to add               | Where it goes                                                           | Contract to satisfy                                                |
| ---------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ |
| A new component (leaf agent)       | `operad/agents/<domain>/components/`                                    | Subclass `Agent[In, Out]`; declare `input`/`output`/`role`/`task`/`rules` as class attributes. |
| A new pre-wired pattern (composite) | `operad/agents/<domain>/<pattern>.py`                                  | Subclass `Agent[In, Out]`; override `forward` as a router (no payload-branching). |
| A new domain                       | `operad/agents/<new_domain>/` with `components/` subdir                 | Mirror the existing domain layout (see `reasoning/`).              |
| A new algorithm                    | `operad/algorithms/<name>.py`                                           | Plain class; `run(...)` signature; takes `Agent`s + metrics as constructor args. |
| A new metric                       | `operad/metrics/<name>.py`                                              | Implement `Metric.score(predicted, expected) -> float`.            |
| A new optimizer                    | `operad/optim/<name>.py`                                                | Subclass `Optimizer`; implement `async step()`.                    |
| A new loss                         | `operad/optim/loss.py` or sibling                                       | Implement `Loss.compute(pred, expected) -> (score, TextualGradient)`. |
| A new sampler                      | `operad/data/<sampler>.py`                                              | Subclass `Sampler`; expose `__iter__`.                             |
| A new observer                     | `operad/runtime/observers/<name>.py`                                    | Subclass `Observer`; register with `runtime.observers.registry`.   |
| A new backend                      | `operad/core/models.py` (and a sibling adapter file)                    | Extend `resolve_model` dispatcher; honor `Configuration.backend`.  |
| A new mutation primitive           | `operad/utils/ops.py`                                                   | Subclass `Op`; implement `apply(agent)` + an undo function.        |
| A new callback                     | `operad/train/callbacks.py`                                             | Subclass `Callback`; override the lifecycle hook(s) you need.      |

When you add anything to the public API, also update
[INVENTORY.md](../INVENTORY.md) — that doc is the agent-facing
capability index, and it must stay accurate.
