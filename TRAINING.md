# TRAINING.md — training agents with `operad.optim`

This tutorial is for a reader who already scanned
[README.md](README.md) and [INVENTORY.md](INVENTORY.md) but has not yet
written a fit loop. By the end you will have built a trainable agent,
picked a loss and an optimizer, run a `Trainer`, checkpointed the
best epoch, and know where to reach for hooks and debugging.

The library mirrors PyTorch at every level: `Parameter → backward →
Optimizer → Trainer`. The twist is that gradients are **text**,
not floats — `TextualGradient` is a Pydantic critique, produced by
LLM-driven critics, that walks the runtime tape and gets applied by
`RewriteAgent`s. You will write the same shape of code you would
with `torch.nn` + `torch.optim`; the language of improvement is
English.

---

## 1. What are we optimizing?

An `Agent`'s declared state is six Pydantic fields:

- `role` — the persona.
- `task` — the one instruction that dominates.
- `rules` — a `list[str]` of hard constraints.
- `examples` — typed `list[Example[In, Out]]` few-shot pairs.
- `config.sampling.temperature`, `config.sampling.top_p` — numeric knobs.
- `config.model`, `config.backend`, `config.io.renderer` — categorical knobs.

Every one of these is wrapped by a `Parameter` subclass:

| Parameter class        | Field(s)                                              |
| ---------------------- | ----------------------------------------------------- |
| `TextParameter`        | `role`, `task`                                        |
| `RuleListParameter`    | `rules`                                               |
| `ExampleListParameter` | `examples`                                            |
| `FloatParameter`       | `temperature`, `top_p`                                |
| `CategoricalParameter` | `model`, `backend`, `renderer`                        |

Each `Parameter` carries an optional `ParameterConstraint`
(`TextConstraint` / `NumericConstraint` / `VocabConstraint` /
`ListConstraint`) that is consulted before every update — the
textual-gradient analogue of gradient clipping.

A gradient is a `TextualGradient`:

```python
class TextualGradient(BaseModel):
    message: str                              # natural-language critique
    by_field: dict[str, str] = {}             # per-field breakdown
    severity: float = 1.0                     # magnitude; 0 = no-op
    target_paths: list[str] = []              # blame-routing hints
```

`severity == 0.0` is the null gradient — "no update needed."

---

## 2. Constructing your first trainable agent

Start with any built agent and flip the fields you want to train:

```python
from operad import Sequential
from operad.agents.reasoning import Planner, Reasoner, Critic

agent = Sequential(Planner(config=cfg), Reasoner(config=cfg), Critic(config=cfg))
agent.mark_trainable(role=True, task=True, rules=True)   # all children
await agent.abuild()

for path, p in agent.named_parameters():
    print(f"{path:40s}  {type(p).__name__:22s}  requires_grad={p.requires_grad}")
```

`mark_trainable` takes the same field-name kwargs (`role`, `task`,
`rules`, `examples`, `temperature`, `top_p`) and broadcasts to every
descendant by default. To target a single descendant, pass a
per-path kwarg:

```python
agent.mark_trainable(**{"stage_1.task": True})   # Reasoner.task only
```

The inverse is `freeze_parameters(...)` (same kwargs).
`trainable_parameters()` yields the `requires_grad=True` subset.

---

## 3. Picking a loss

A `Loss` produces `(score: float, gradient: TextualGradient)`. The
`Metric` protocol gives you `score` for free; `operad.optim` gives
you four standard ways to get a gradient as well:

```python
from operad.optim.losses import (
    LLMAAJ, MetricLoss, SchemaLoss, CompositeLoss,
)

# Deterministic metric → auto-generated critique
loss_exact = MetricLoss(ExactMatch())

# LLM rubric judge → the judge's rationale becomes the critique
loss_rubric = LLMAAJ(judge)

# Shape-conformance check
loss_shape = SchemaLoss(Answer)

# Weighted combination
loss_fn = CompositeLoss([
    (loss_rubric, 1.0),
    (loss_shape, 0.2),
])
```

`LLMAAJ` is the most common choice — wrap any
`Agent[Candidate[In, Out], Score]` and the judge's
`Score.rationale` becomes the gradient's `message`.

---

## 4. The fit loop in one page

Every training run has the same shape:

```python
import operad
from operad import Sequential
from operad.optim.losses import LLMAAJ
from operad.optim.optimizers.tgd import TextualGradientDescent
from operad.optim.schedulers.lr import CosineExplorationLR
from operad.train import Trainer, EarlyStopping, BestCheckpoint
from operad.data import DataLoader, random_split

# 1. Build the agent and mark what's trainable.
agent = Sequential(Planner(...), Reasoner(...), Critic(...))
agent.mark_trainable(role=True, task=True, rules=True)
await agent.abuild()

# 2. Split the dataset.
train, val = random_split(dataset, [0.8, 0.2], seed=0)
loader = DataLoader(train, batch_size=8, shuffle=True)

# 3. Loss, optimizer, scheduler.
loss_fn   = LLMAAJ(judge)
optimizer = TextualGradientDescent(agent.parameters(), lr=1.0)
scheduler = CosineExplorationLR(optimizer, T_max=10)

# 4. Compose the trainer.
trainer = Trainer(
    agent, optimizer, loss_fn,
    scheduler=scheduler,
    callbacks=[BestCheckpoint(monitor="val_loss", mode="min")],
    accumulation_steps=2,
)

# 5. Run.
report = await trainer.fit(
    loader,
    val_ds=val,
    epochs=5,
    early_stopping=EarlyStopping(monitor="val_loss", patience=2),
)

print("best epoch:", report.best_epoch, "hash:", report.best_hash_content)
```

Per sample: `tape()` opens, the agent runs, the loss fires,
`backward()` walks the tape in reverse, each `Parameter.grad` fills
in. Per batch of `accumulation_steps` samples: per-sample gradients
merge (messages joined with `\n---\n`, `target_paths` unioned,
`severity` = max) and `optimizer.step()` applies the merged gradient
to every trained `Parameter`. At epoch end: validation, scheduler
step, callback fan-out.

---

## 5. Picking an optimizer

| Optimizer                  | Reach for it when…                                                       |
| -------------------------- | ------------------------------------------------------------------------ |
| `TextualGradientDescent`   | Small step count, clear critiques, one parameter at a time.              |
| `MomentumTextGrad`         | Gradients are noisy batch-to-batch; want smoothing across steps.         |
| `EvoGradient`              | Categorical / structural choices; population search beats single rewrites.|
| `OPROOptimizer`            | Long-horizon instruction tuning; optimizer keeps a history window.       |
| `APEOptimizer`             | Ample compute budget; sample many candidates and rank.                   |

All five subclass a shared `Optimizer` base, take a
`list[Parameter] | list[ParamGroup]`, and expose `zero_grad()` +
`async step()`. `ParamGroup`s let you give different `lr` /
`momentum` / constraint overrides to different slices of the
parameter list:

```python
optimizer = MomentumTextGrad([
    {"params": list(agent.parameters(recurse=False)), "lr": 1.0},
    {"params": list(agent._children["critic"].parameters()), "lr": 0.3},
])
```

---

## 6. Schedulers and when they matter

In operad, **`lr` is the aggression knob a `RewriteAgent` reads** —
low `lr` nudges a `Parameter`'s value, high `lr` rewrites it. The
schedulers mirror `torch.optim.lr_scheduler` so your intuition ports
directly:

| Scheduler              | Use when…                                                 |
| ---------------------- | --------------------------------------------------------- |
| `ConstantLR`           | Baseline; you want no annealing at all.                   |
| `StepLR`               | Drop by `gamma` every `step_size` epochs.                 |
| `MultiStepLR`          | Pre-picked milestones (e.g. cool off after epoch 3 and 7).|
| `ExponentialLR`        | Smooth multiplicative decay every epoch.                  |
| `CosineExplorationLR`  | Anneal from explore-heavy to refine-heavy over a budget.  |
| `WarmupLR`             | First few epochs at a low lr to stabilize.                |
| `ReduceLROnPlateau`    | Monitor val_loss; back off when it stalls.                |
| `ChainedScheduler`     | Combine several annealers (e.g. warmup + cosine).         |
| `SequentialLR`         | Hand off between schedulers at epoch milestones.          |

All schedulers except `ReduceLROnPlateau` take `(optimizer,
last_epoch=-1)` plus their own kwargs and step once per epoch inside
`Trainer.fit`. `state_dict()` / `load_state_dict()` are live for
checkpointing.

---

## 7. Callbacks and checkpointing

Callbacks attach at `Trainer` construction or via the
`fit(..., early_stopping=...)` kwarg:

```python
from operad.train import (
    BestCheckpoint, EarlyStopping, GradClip,
    LRLogger, MemoryRotation, PromptDrift,
)

trainer = Trainer(
    agent, optimizer, loss_fn,
    callbacks=[
        BestCheckpoint(monitor="val_loss", mode="min"),
        GradClip(max_severity=0.8),
        PromptDrift(),                    # per-epoch prompt hash + diff
        LRLogger(),
        MemoryRotation(max_tape_entries=4096),
    ],
)

await trainer.fit(
    loader, val_ds=val, epochs=10,
    early_stopping=EarlyStopping(monitor="val_loss", patience=3),
)
```

| Callback              | What it does                                                     |
| --------------------- | ---------------------------------------------------------------- |
| `EarlyStopping`       | Halts when a monitored metric stops improving for `patience`.    |
| `BestCheckpoint`      | Tracks the best epoch's `hash_content`.                          |
| `GradClip`            | Caps `TextualGradient.severity` per step.                        |
| `PromptDrift`         | Logs each epoch's prompt-hash delta from the seed.               |
| `LRLogger`  | Records per-group `lr` at every epoch boundary.                  |
| `MemoryRotation`      | Rotates the oldest tape entries to bound long-run memory.        |

`TrainingReport.best_hash_content` gives you a content-addressable
handle on the agent at its best epoch — feed it back to
`agent.load_state(...)` or look it up in a cassette later.

---

## 8. Debugging: hooks and `no_grad()`

Three per-agent hooks are live, all returning a `Handle` with
`.remove()`:

```python
h1 = agent.register_forward_pre_hook(lambda a, x: None)
h2 = agent.register_forward_hook(lambda a, x, y: print(a.name, y))
h3 = agent.register_backward_hook(lambda a, grad: None)
# ... later: h1.remove(); h2.remove(); h3.remove()
```

Use them for payload logging, grad inspection, and lightweight
instrumentation without subclassing. Hooks are skipped during
`build()` tracing and under `inference_mode()`.

For inference-only passes that should not record gradients:

```python
from operad.optim.gradmode import no_grad

async with no_grad():
    out = await agent(x)           # no tape entries written
```

For a structured view of *which* parameter took blame for *which*
sample, use `PromptTraceback`:

```python
from operad.optim.backprop.tape import tape
from operad.optim.backprop import traceback as ptb

async with tape() as t:
    out = await agent(x)
score, loss = await loss_fn.compute(out.response, expected)
tb = ptb.PromptTraceback.from_run(t, loss)
print(str(tb))                  # plain-text stanzas (stdlib only)
print(tb.to_markdown())         # PR-body friendly
tb.save("traceback.ndjson")     # NDJSON, one frame per line
```

Each frame carries the agent path, depth, leaf-or-composite flag,
input/output payloads, the rendered prompt, and the per-node
gradient. See [INVENTORY.md §22](INVENTORY.md#22-prompttraceback) and
[`operad/optim/backprop/traceback.py`](operad/optim/backprop/traceback.py).

---

## 9. Reproducibility: cassettes and determinism

Every `optimizer.step()` rewrites one or more `Parameter`s and
produces a new `hash_content` on the agent (see §20 of
[INVENTORY.md](INVENTORY.md)). Two consequences:

- **Best-epoch pinning.** `TrainingReport.best_hash_content` is the
  content-addressable identity of the agent after the best epoch. A
  later run can hash-match to reach the same state.
- **Cassette replay.** Offline training runs can be fully recorded
  via `OPERAD_CASSETTE=record` and replayed deterministically — no
  live LLM calls required, either for the learner's forward passes
  or for LLM-driven optimizers. The full validation matrix for
  offline-deterministic training is still on the roadmap.

Determinism invariants: `random_split(..., seed=0)` + fixed
sampler + no temperature on the agents under training ⇒ reproducible
fit loop to the hash.

---

## 10. Observability and human feedback

`Trainer.fit` emits lifecycle events on operad's observer registry, so
training is visible wherever the agent graph already is:

- **Terminal.** `TrainerProgressObserver` (from `operad.train`)
  renders a Rich progress bar with nested epoch + batch bars. It
  consumes `algo_start`/`iteration`/`algo_end` events from `Trainer`
  plus `batch_start`/`batch_end` from `DataLoader`.
- **Web dashboard.** `operad-dashboard` mounts four per-run panels
  under `GET /runs/{run_id}`: fitness curve, mutation heatmap,
  `PromptDrift` timeline, training progress. They all share the
  same bounded event buffer inside `WebDashboardObserver`.
- **Disk / external.** `JsonlObserver` and `OtelObserver` carry the
  same events; no training-specific plumbing required.

```python
from operad import dashboard as operad_dashboard
from operad.runtime.observers import registry
from operad.train import TrainerProgressObserver

registry.register(TrainerProgressObserver())
operad_dashboard.attach(port=7860)  # if dashboard is running

report = await trainer.fit(loader, epochs=5)
```

The `PromptDrift` callback emits an `AlgorithmEvent(kind="iteration",
algorithm_path="PromptDrift")` per epoch with `hash_before`,
`hash_after`, and `changed_params`, so the dashboard's drift panel
turns silent prompt evolution into a scannable timeline.

### Human-in-the-loop training with Studio

`HumanFeedbackCallback` dumps one NDJSON row per validation sample
during `Trainer.fit`; `apps/studio/` lets a human rate those rows in
the browser and re-launches training with `HumanFeedbackLoss` as the
loss:

```python
from operad.optim.losses import HumanFeedbackLoss
from operad.train import HumanFeedbackCallback, Trainer

# Round 1 — dump unrated rows for labeling.
trainer = Trainer(agent, optimizer, loss_fn,
                  callbacks=[HumanFeedbackCallback("hf.jsonl")])
await trainer.fit(loader, val_ds=val, epochs=1)
trainer.save("talker.json")

# Human labels hf.jsonl via `operad-studio --data-dir . --agent-bundle talker.json`.

# Round 2 — train on ratings.
trainer2 = Trainer.load(
    "talker.json",
    loss_fn=HumanFeedbackLoss("hf.jsonl"),
    optimizer_factory=lambda a: TextualGradientDescent(a.parameters(), lr=1.0),
)
await trainer2.fit(loader, epochs=3)
```

Rows whose rating is null → `HumanFeedbackLoss` returns a neutral
score with a null gradient, so the trainer still counts the sample
but applies no pressure — the agent only gets feedback on outputs
the human has actually rated.

---

## 11. Further reading

- [`operad/optim/README.md`](operad/optim/README.md) — the optim-layer
  design doc: the four-word spine, the full dependency graph, the
  non-goals.
- [`operad/train/README.md`](operad/train/README.md) — the `Trainer`
  fit-loop wrapper that orchestrates this stack.
- [`apps/demos/agent_evolution/run.py`](apps/demos/agent_evolution/run.py)
  — a fully-offline, deterministic showcase of
  agents-optimizing-agents: a seed agent evolved over N generations,
  driven by `Agent.auto_tune` on the algorithm side. The
  `Trainer`-driven fit loop above is the equivalent pathway on the
  `operad.optim` / `operad.train` side.
- [INVENTORY.md §21](INVENTORY.md#21-training--optimization) — the
  catalog entry with every exported symbol.
- Yuksekgonul et al. (2024), *TextGrad: Automatic Differentiation
  via Text* — the textual-gradient idea.
- Zhou et al. (2022), *Large Language Models Are Human-Level Prompt
  Engineers* — APE.
- Yang et al. (2023), *Large Language Models as Optimizers* — OPRO.
