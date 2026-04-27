# operad.train — the fit loop

PyTorch-Lightning analog. `Trainer` glues a built `Agent`, an
`Optimizer`, a `Loss`, an optional LR scheduler, metrics, and
callbacks into a single `fit()` call that returns a `TrainingReport`.

The optimizer / loss / parameter / backward machinery lives in
[`../optim/`](../optim/README.md). This package wraps it in a
familiar fit loop so the *training* surface mirrors `pytorch-lightning`
the same way the *inference* surface mirrors `torch.nn`.

---

## Files

| File                        | Role                                                                              |
| --------------------------- | --------------------------------------------------------------------------------- |
| `trainer.py`                | `Trainer.fit / evaluate / predict`. The orchestrator.                             |
| `callbacks/`                | `Callback` base + `EarlyStopping`, `BestCheckpoint`, `GradClip`, `PromptDrift`, `LRLogger`, `MemoryRotation`, `HumanFeedbackCallback`, `TracebackOnFailure`. |
| `progress.py`               | `TrainerProgressObserver` — Rich nested progress bars.                            |
| `report.py`                 | `EpochReport`, `TrainingReport` — structured outputs.                             |

## Public API

```python
from operad.train import (
    Trainer,
    Callback,
    EarlyStopping,
    BestCheckpoint, GradClip, PromptDrift,
    LRLogger, MemoryRotation,
    HumanFeedbackCallback,
    TrainerProgressObserver,
    EpochReport, TrainingReport,
)
from operad.optim.losses import HumanFeedbackLoss
```

## Smallest meaningful example

```python
from operad import Sequential
from operad.optim.losses import LLMAAJ
from operad.optim.optimizers.tgd import TextualGradientDescent
from operad.optim.schedulers.lr import CosineExplorationLR
from operad.train import Trainer, EarlyStopping, BestCheckpoint
from operad.data import DataLoader, random_split

agent = Sequential(Planner(...), Reasoner(...), Critic(...))
agent.mark_trainable(role=True, task=True, rules=True)
await agent.abuild()

train, val = random_split(dataset, [0.8, 0.2], seed=0)
loader = DataLoader(train, batch_size=8, shuffle=True)

trainer = Trainer(
    agent,
    TextualGradientDescent(agent.parameters(), lr=1.0),
    LLMAAJ(judge),
    scheduler=CosineExplorationLR(... , T_max=10),
    callbacks=[
        BestCheckpoint(monitor="val_loss", mode="min"),
        PromptDrift(),
    ],
    accumulation_steps=2,
)

report = await trainer.fit(
    loader, val_ds=val, epochs=5,
    early_stopping=EarlyStopping(monitor="val_loss", patience=2),
)
print("best epoch:", report.best_epoch, "hash:", report.best_hash_content)
```

Per sample: `tape()` opens, the agent runs, the loss fires,
`backward()` walks the tape, each `Parameter.grad` fills in. Per batch
of `accumulation_steps` samples: per-sample gradients merge onto each
`Parameter.grad` and `optimizer.step()` applies them. At epoch end:
validation, scheduler step, callback fan-out.

## Callbacks

| Callback                | Effect                                                                       |
| ----------------------- | ---------------------------------------------------------------------------- |
| `EarlyStopping`         | Halts when a monitored metric stops improving for `patience`.                |
| `BestCheckpoint`        | Tracks the best epoch's `hash_content`.                                      |
| `GradClip`              | Caps `TextualGradient.severity` per step.                                    |
| `PromptDrift`           | Per-epoch prompt-hash delta + changed param paths; emits dashboard events.   |
| `LRLogger`              | Records each group's `lr` at every epoch boundary.                           |
| `MemoryRotation`        | Bounds tape memory growth on long runs by rotating old entries.              |
| `HumanFeedbackCallback` | Dumps per-validation `(input, predicted)` rows to NDJSON for human rating.   |

## Human-in-the-loop

`HumanFeedbackCallback` writes one NDJSON row per validation sample
during `Trainer.fit`; [`apps/studio/`](../../apps/studio/README.md)
lets a human assign 1–5 ratings in the browser; relaunching with
`HumanFeedbackLoss(ratings_path)` trains on those ratings. Rows whose
rating is null are counted but apply no pressure (null gradient), so
the agent only gets feedback on outputs the human has rated.

## Observability

`Trainer.fit` emits lifecycle events on operad's observer registry, so
training is visible wherever inference already is:

- `TrainerProgressObserver` — terminal Rich bars (nested epoch + batch).
- `apps/dashboard/` — four per-run panels at `GET /runs/{run_id}`:
  fitness curve, mutation heatmap, `PromptDrift` timeline, training
  progress.
- `JsonlObserver`, `OtelObserver` — same events on disk / over OTel.

## How to extend

| What                | Where                                                                   |
| ------------------- | ----------------------------------------------------------------------- |
| A new callback      | `callbacks/` — subclass `Callback`; override the lifecycle hook(s).     |
| A new loss          | [`../optim/losses/`](../optim/losses/).                                 |
| A new optimizer     | [`../optim/`](../optim/README.md).                                      |
| A new progress UI   | `progress.py` — register on the observer registry.                      |

## Related

- [`../optim/`](../optim/README.md) — the textual-gradient training
  spine that `Trainer` orchestrates.
- [`../../TRAINING.md`](../../TRAINING.md) — end-to-end training
  walkthrough.
- [`apps/dashboard/`](../../apps/dashboard/README.md) — the live UI.
- [`apps/studio/`](../../apps/studio/README.md) — human labeling.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §21 — exhaustive
  training surface.
