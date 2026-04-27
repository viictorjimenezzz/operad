# operad.optim — training & optimization for agents

`operad.optim` is the textual-gradient training stack: first-class
`Parameter` handles over mutable agent state (`role`, `task`, `rules`,
`examples`, sampling), a runtime tape + `backward()` walker that
distributes a `TextualGradient` through the `AgentGraph`, and an
optimizer fleet that applies those gradients via LLM-driven rewrite
agents. The surface mirrors `torch.optim` (`Parameter` →
`backward()` → `Optimizer` → scheduler), but the gradient is a
Pydantic critique in natural language, not a float.

The fit-loop wrapper (`Trainer.fit / evaluate / predict`) lives in
[`../train/`](../train/README.md). For an end-to-end walkthrough see
[`../../TRAINING.md`](../../TRAINING.md).

---

## The four-word spine

```
Parameter     —  a handle on a trainable field of an Agent
backward()    —  walks the AgentGraph runtime tape, populates .grad on each Parameter
Optimizer     —  consumes (Parameter, grad) pairs, rewrites the Parameter's value
Trainer       —  the fit/evaluate/predict loop that glues it all together
```

If you've used PyTorch, the following should feel familiar:

```python
import operad
from operad.optim.losses import LLMAAJ
from operad.optim.optimizers.tgd import TextualGradientDescent
from operad.optim.schedulers.lr import CosineExplorationLR
from operad.train import Trainer
from operad.data import DataLoader, random_split

agent = Sequential(Planner(...), Reasoner(...), Critic(...))
agent.mark_trainable(role=True, task=True, rules=True)
await agent.abuild()

train, val = random_split(dataset, [0.8, 0.2])
loader     = DataLoader(train, batch_size=8, shuffle=True)

loss_fn   = LLMAAJ(judge)
optimizer = TextualGradientDescent(agent.parameters(), lr=1.0)
scheduler = CosineExplorationLR(optimizer, T_max=10)

trainer = Trainer(agent, optimizer, loss_fn, scheduler=scheduler)
trained = await trainer.fit(loader, val_ds=val, epochs=5)
```

The output `trained` is a freshly-built `Agent` with a distinct
`hash_content` — content-addressable, freezable via `freeze()`,
diffable via `diff()`.

---

## The key abstractions

### `Parameter`

A view onto a single mutable field of an agent (`agent.role`,
`agent.rules[2]`, `agent.config.sampling.temperature`, ...). The
field lives on the agent; `Parameter` is just a handle the optimizer
holds. Every `Parameter` carries a `path`, a `kind`, the current
`value`, a `requires_grad` flag, and a slot for `grad` populated by
`backward()`.

Subclasses specialize the `value` type:

- `TextParameter` — `role`, `task` (`str`)
- `RuleListParameter` — `rules` (`list[str]`)
- `ExampleListParameter` — `examples` (`list[Example[In, Out]]`)
- `FloatParameter` — `temperature`, `top_p` (`float` with bounds)
- `CategoricalParameter` — `model`, `backend`, `renderer` (`str` with vocab)

Each subclass can carry a `ParameterConstraint` (bounds, vocab, max
length) that the optimizer consults before accepting an update —
the textual-gradient analog of gradient clipping.

### `TextualGradient`

A Pydantic structured critique:

- `message: str` — the natural-language "how this should change"
- `by_field: dict[str, str]` — per-field breakdown when applicable
- `severity: float` — magnitude; 0 means "no update needed"
- `target_paths: list[str]` — optional blame-routing hints

### `Loss`

Protocol that extends `Metric` with a `compute()` returning
`(score, TextualGradient)`. Any existing `Metric` lifts for free via
`MetricLoss(metric)`. LLM judges (the existing `Critic`) become
losses via `LLMAAJ(critic)`: `Score.score` → float, `Score.rationale`
→ gradient text.

### `Tape` and `backward()`

`operad.optim.backprop.tape()` is a context manager that installs a
`TapeObserver` on the existing observer registry. Every `Agent.invoke`
call inside the context records a `TapeEntry` (agent reference,
input, output, rendered prompt). The tape is an ordered list of
entries in call order; `backward(loss)` walks it in reverse,
propagating a `TextualGradient` through each node and computing the
per-parameter gradient.

Propagation rules mirror the structural primitives:

| Primitive  | Backward rule                                                  |
| ---------- | -------------------------------------------------------------- |
| Leaf       | Compute per-parameter grad from (prompt, input, output, grad_out)  |
| `Sequential` | Propagate grad sequentially back through each stage            |
| `Parallel` | Distribute grad to each branch, possibly weighted by `combine` |
| `Switch`   | Backprop only into the branch actually taken                   |
| `Debate`   | Distribute grad to proposers weighted by critic rationales     |

The gradient agents (`BackpropAgent`) and rewrite agents
(`RewriteAgent`) are themselves `Agent` subclasses — so they reuse
the whole cassette / hashing / observer stack.

### `Optimizer`

Base class with `zero_grad()` and `async step()`. Takes a list of
`Parameter`s or parameter-group dicts (per-group `lr`, `momentum`,
constraint overrides). Subclasses:

- `TextualGradientDescent` — naive rewrite per parameter
- `MomentumTextGrad` — running summary of recent gradients
- `EvoGradient` — mutation-selection (replaces the legacy `Evolutionary`)
- `OPROOptimizer` — LLM-as-optimizer with history window
- `APEOptimizer` — sample-and-rank candidate rewrites

### `Trainer`

`operad.train.Trainer(agent, optimizer, loss_fn, ...)` exposes
`fit(loader, val, epochs, ...)`, `evaluate(ds)`, `predict(x)`. Supports
callbacks (`EarlyStopping`, `BestCheckpoint`, `GradClip`,
`PromptDrift`, `LRLogger`). Batching, gradient accumulation,
LR scheduling, validation, checkpointing — the whole standard fit
loop.

### `DataLoader` + `random_split`

Batched / shuffled / optionally-sandboxed iteration over the existing
`operad.benchmark.Dataset`. `random_split(ds, [0.8, 0.2])` for
train/val slicing.

### Hooks, `no_grad()`, `state_dict()`

- `agent.register_forward_hook(fn)`, `register_forward_pre_hook(fn)`,
  `register_backward_hook(fn)` — per-agent instrumentation handles
  with `handle.remove()`.
- `async with operad.optim.gradmode.no_grad(): ...` disables tape recording, speeds
  up inference.
- `agent.state_dict()` / `load_state_dict(sd)` are PyTorch-muscle
  aliases for `state()` / `load_state()`.

---

## The dependency graph (for agents implementing tasks)

```
       1-1 Parameter ─────────────────┐
                                      ├──> 2-1 Agent surface (parameters, hooks, no_grad)
                                      ├──> 2-2 Loss (uses TextualGradient)
                                      ├──> 2-4 BackpropAgent (uses TextualGradient)
                                      │
       1-2 DataLoader ────────────────┤
                                      ├──> 2-3 RewriteAgent (independent)
                                      ├──> 2-5 Tape (independent)
                                      │
   2-{1..5} ──────────────────────────┼──> 3-1 backward() (uses Tape, Loss, BackpropAgent)
                                      └──> 3-2 Optimizer base + TGD (uses Parameter, RewriteAgent)

   3-{1,2} ──────────────────────────┬──> 4-1 Optimizer fleet (Momentum, Evo, OPRO, APE)
                                     ├──> 4-2 LR schedulers
                                     └──> 4-3 Trainer + callbacks (uses Optimizer, Loss, DataLoader)

   4-{1,2,3} ───────────────────────┬──> 5-1 Offline train demo
                                     ├──> 5-2 Docs updates
                                     ├──> 5-3 state_dict / freeze integration
                                     ├──> 5-4 PromptTraceback
                                     └──> 5-5 Cassette replay validation
```

Within each sequential wave (`1-*`, `2-*`, `3-*`, `4-*`, `5-*`) every
task operates on disjoint files and can safely run in parallel.

---

## Non-goals

- Numerical gradient estimation (finite differences). Could come
  later if a strong use case emerges; not needed for the TextGrad-
  style flow.
- Changing the *topology* of the agent tree via an optimizer. `Parameter`
  is over node *contents*, not structure. Topology edits happen via
  `Evolutionary`/`Sweep`/hand edits.
- Training model weights. We train *prompts + sampling knobs*, not
  model parameters. `operad` is an orchestration library, not a
  training framework for LLMs.

---

## Further reading

- [`../train/README.md`](../train/README.md) — the `Trainer` fit-loop
  wrapper that orchestrates this stack.
- [`../../TRAINING.md`](../../TRAINING.md) — end-to-end training
  tutorial.
- [`../../VISION.md`](../../VISION.md) §3 — why prompt-level training
  is the right unit.
- Yuksekgonul et al. (2024), *TextGrad: Automatic Differentiation via Text* — the textual-gradient idea.
- Zhou et al. (2022), *Large Language Models Are Human-Level Prompt Engineers* — APE.
- Yang et al. (2023), *Large Language Models as Optimizers* — OPRO.

---

## Status

The stack is shipped end-to-end. `Parameter` (with all five typed
subclasses + constraints), `tape` / `backward`, the full `Optimizer`
fleet (`TextualGradientDescent`, `MomentumTextGrad`, `EvoGradient`,
`OPROOptimizer`, `APEOptimizer`), every LR scheduler, hooks +
`no_grad()` + `inference_mode()`, `BackpropAgent`, `RewriteAgent`,
and `PromptTraceback` are all live. The `Trainer` glue lives in
[`../train/`](../train/README.md).

Remaining tracked item: cassette-replay determinism validation —
the full validation matrix for offline-deterministic training under
`OPERAD_CASSETTE=record/replay`.
