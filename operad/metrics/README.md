# operad.metrics — pluggable scorers

A `Metric` is anything with an async `score(predicted, expected) ->
float` method. Two flavors ship today: deterministic Python (cheap,
exact) and LLM judges via `RubricCritic` (subjective, flexible).
`CostTracker` is a special-case observer-style aggregator — sums
per-run cost across the observer registry rather than scoring a single
prediction.

Metrics are the feedback signal that closes every algorithm loop and
every fit loop.

---

## Files

| File                | Role                                                                             |
| ------------------- | -------------------------------------------------------------------------------- |
| `base.py`           | The `Metric` protocol.                                                           |
| `deterministic.py`  | `ExactMatch`, `JsonValid`, `Latency`.                                            |
| `contains.py`       | `Contains(expected_substring)`.                                                  |
| `regex_match.py`    | `RegexMatch(pattern)`.                                                           |
| `rouge.py`          | `Rouge1` — F1 over text fields.                                                  |
| `rubric_critic.py`  | `RubricCritic(critic_agent)` — wraps an `Agent[Candidate, Score]`.               |
| `cost.py`           | `CostTracker` — observer-style aggregator across runs.                           |

## Public API

```python
from operad.metrics import (
    Metric,
    ExactMatch, Contains, RegexMatch, JsonValid, Rouge1, Latency,
    RubricCritic, CostTracker,
)
```

## Smallest meaningful examples

**Deterministic.**

```python
from operad.metrics import ExactMatch
em = ExactMatch()
score = await em.score(predicted=A(answer="4"), expected=A(answer="4"))   # 1.0
```

**LLM judge.**

```python
from operad.metrics import RubricCritic
from operad.agents.reasoning import Critic

critic = Critic(config=cfg, ...)            # Agent[Candidate[Q, A], Score]
metric = RubricCritic(critic)
score  = await metric.score(predicted, expected)   # judge.rationale captured separately
```

`RubricCritic` is the bridge between a metric and a `Loss`: the same
critic that scores predictions also produces a `TextualGradient` when
lifted into `JudgeLoss(critic)` under
[`../optim/losses/`](../optim/losses/).

## How to extend

A new metric satisfies the `Metric` protocol:

```python
from operad.metrics import Metric

class MyMetric:
    async def score(self, predicted, expected) -> float:
        return ...
```

That's the whole contract. For LLM judges, write a `Critic`
`Agent[Candidate, Score]` and wrap with `RubricCritic`.

`AggregatedMetric` (in [`../benchmark/`](../benchmark/README.md))
reduces a list of per-row scores via `mean`/`median`/`min`/`max`/`sum`
when you want a multi-row summary metric.

## Related

- [`../benchmark/`](../benchmark/README.md) — `evaluate(agent, ds,
  metrics)` is the canonical entry point.
- [`../optim/`](../optim/README.md) — `MetricLoss(metric)` and
  `JudgeLoss(critic)` lift any metric into a textual-gradient loss.
- [`../algorithms/`](../algorithms/README.md) — algorithms take
  metrics as parameters for inner-loop selection.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §8 — full
  metric catalog.
