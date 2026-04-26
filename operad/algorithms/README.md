# operad.algorithms — outer loops

Algorithms orchestrate `Agent`s through outer loops with metric
feedback. They are deliberately **not** `Agent` subclasses — their
natural API is not `__call__(x: In) -> Out`. Each one is a plain class
with whatever `run(...)` signature its task needs, taking agents and
metrics as constructor arguments.

This is the algorithmic layer of "agents improving agents". The same
idea formalized into a fit loop lives in
[`../optim/`](../optim/README.md) + [`../train/`](../train/README.md).

---

## Files

| File                | Class(es)                                                          | What it does |
| ------------------- | ------------------------------------------------------------------ | ------------ |
| `beam.py`           | `Beam`                                                             | Best-of-N over candidate generations; pick top-K by metric. |
| `debate.py`         | `Debate`                                                           | Multi-agent debate: `Proposer` + `DebateCritic` rounds, `Synthesizer` final. |
| `sweep.py`          | `Sweep`, `SweepCell`, `SweepReport`                                | Cartesian grid search over dotted-path parameters of a seed agent. |
| `srefine.py`        | `SelfRefine`, `RefineInput`, `SelfRefineState`                     | Generate → reflect → refine until accept or `max_iter`. |
| `autoresearch.py`   | `AutoResearcher`, `ResearchPlan`, `ResearchInput`, `ResearchContext` | Plan → retrieve → reason → critique → reflect, wrapped in best-of-N. |

## Public API

```python
from operad.algorithms import (
    AutoResearcher, ResearchContext, ResearchInput, ResearchPlan,
    Beam,
    Debate,
    Sweep, SweepCell, SweepReport,
    SelfRefine, RefineInput, SelfRefineState,
)
```

## Smallest meaningful examples

**Best-of-N.**

```python
from operad.algorithms import Beam
from operad.metrics import RubricCritic

beam = Beam(generator=reasoner, critic=RubricCritic(critic), n=5)
best = await beam.run(Q(text="Explain entropy."))
```

**Sweep.**

```python
from operad.algorithms import Sweep
sweep = Sweep(
    seed=agent,
    grid={
        "stage_0.config.sampling.temperature": [0.0, 0.3, 0.7],
        "stage_0.role": ["Be terse.", "Be discursive."],
    },
    metric=ExactMatch(),
)
report = await sweep.run(dataset)
```

**Debate.**

```python
from operad.agents.debate import DebateTopic
from operad.algorithms import Debate

result = await Debate(rounds=3).run(DebateTopic(topic="Should I buy the car?"))
```

## How to extend

A new algorithm is a plain class. There is no base class to inherit
from; the contract is structural:

1. Take agents and metrics as constructor args (default to sensible
   class-level attributes so subclasses can swap components).
2. Expose an async `run(...)` whose return type reflects the
   algorithm's purpose (`-> Out`, `-> Agent`, `-> Report`, …).
3. Fire `AlgorithmEvent`s on the observer registry at lifecycle points
   (`algo_start`, `iteration`, `algo_end`) so dashboards and JSONL
   logs see the loop.

Components are class-level defaults; callers supply only the
algorithm's own knobs at construction time. To swap a component,
subclass and override the class attribute.

## Why algorithms are not `Agent`s

Forcing every outer loop into the `Agent[In, Out]` mold loses
information and produces awkward constructors. `Evolutionary.run() ->
Agent` (an algorithm whose output is an agent) does not fit the
`Agent[In, Out]` mold. `Sweep` returns a `SweepReport`. `Debate`
returns a synthesis. By keeping algorithms as plain classes we avoid
ceremony and let signatures be honest.

## Related

- [`../agents/`](../agents/README.md) — components used as parameters.
- [`../metrics/`](../metrics/README.md) — feedback signal.
- [`../optim/`](../optim/README.md) — the same "improve an agent"
  pattern, formalized into a fit loop. `EvoGradient` is the
  evolutionary search lifted into the optimizer fleet.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §7 — full
  algorithm catalog.
