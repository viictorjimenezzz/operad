# operad.data — iteration + sampling

PyTorch-style data plumbing for the training loop. `DataLoader`
batches and shuffles a `Dataset`; samplers decide ordering;
`random_split` slices for train/val. The active-learning hook is
`UncertaintySampler`, which biases batches toward high-uncertainty
examples — a textual-gradient analogue of hard-example mining.

---

## Files

| File         | Role                                                                                 |
| ------------ | ------------------------------------------------------------------------------------ |
| `loader.py`  | `DataLoader`, `Batch`, `Sampler` protocol, `SequentialSampler`, `RandomSampler`, `WeightedRandomSampler`. |
| `active.py`  | `UncertaintySampler` — biases batches by recent per-row uncertainty signal.          |
| `split.py`   | `random_split(ds, fractions, seed=...)` — deterministic train/val/test slicing.      |

## Public API

```python
from operad.data import (
    DataLoader, Batch,
    Sampler, SequentialSampler, RandomSampler, WeightedRandomSampler,
    UncertaintySampler,
    random_split,
)
```

## Smallest meaningful example

```python
from operad.data import DataLoader, random_split

train, val = random_split(dataset, [0.8, 0.2], seed=0)
loader = DataLoader(train, batch_size=8, shuffle=True)

async for batch in loader:
    # batch.inputs : list[In]
    # batch.expected : list[Out]
    ...
```

## Active learning

```python
from operad.data import UncertaintySampler

sampler = UncertaintySampler(dataset)         # default: equal weight initially
loader  = DataLoader(dataset, batch_size=8, sampler=sampler)

# After each epoch the sampler reads per-row uncertainty signals
# from observer events and reweights the next batch.
```

## How to extend

| What                | Where                                                                        |
| ------------------- | ---------------------------------------------------------------------------- |
| A custom sampler    | Subclass `Sampler`; expose `__iter__`. Pass via `DataLoader(sampler=...)`.   |
| A custom batch type | Subclass `Batch`; thread through your `DataLoader` subclass.                 |

## Related

- [`../benchmark/`](../benchmark/README.md) — `Dataset` / `Entry` are
  the inputs `DataLoader` iterates over.
- [`../train/`](../train/README.md) — `Trainer.fit(loader, ...)` is
  the primary consumer.
- [`../optim/`](../optim/README.md) — gradients are accumulated per
  batch (`Trainer.accumulation_steps`).
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §21 (Data
  subsection) — full surface.
