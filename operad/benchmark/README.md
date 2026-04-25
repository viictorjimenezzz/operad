# operad.benchmark — typed evaluation

Datasets are first-class. Metrics are composable. Sensitivity and
regression checks are built in. This submodule is the harness for
scoring an agent against a dataset reproducibly.

The whole package is `core/` + `metrics/` + `data/` glued together
into the canonical `evaluate(agent, dataset, metrics) -> EvalReport`
entry point.

---

## Files

| File              | Role                                                                              |
| ----------------- | --------------------------------------------------------------------------------- |
| `dataset.py`      | `Dataset[Example]` — typed collection with name, version, content hash.           |
| `entry.py`        | `Entry(input, expected_output, metadata, metric_overrides)`.                      |
| `evaluate.py`     | `evaluate(agent, dataset, metrics) -> EvalReport`. The canonical entry point.     |
| `aggregated.py`   | `AggregatedMetric(metric, reducer)` — reduce per-row scores to one number.        |
| `experiment.py`   | `Experiment` — bundle of (configurations × agent × dataset) for sweeps.           |
| `sensitivity.py`  | `sensitivity(agent, ds, perturbations, metric) -> SensitivityReport`.             |
| `regression.py`   | `regression_check(prev, curr, threshold) -> RegressionReport`.                    |

## Public API

```python
from operad.benchmark import (
    Dataset, Entry,
    evaluate, EvalReport,
    AggregatedMetric, Reducer,
    Experiment,
    sensitivity, SensitivityCell, SensitivityReport,
    regression_check, RegressionReport,
)
```

## Smallest meaningful example

```python
from operad.benchmark import Dataset, Entry, evaluate
from operad.metrics import ExactMatch

ds = Dataset(
    [
        Entry(input=Q(text="2+2"), expected_output=A(answer="4")),
        Entry(input=Q(text="capital of France"), expected_output=A(answer="Paris")),
    ],
    name="trivia", version="v1",
)

report = await evaluate(agent, ds, [ExactMatch()])
print(report.summary)        # {"exact_match": 1.0}
print(report.hash_dataset)   # stable content hash
```

## Sensitivity and regression

```python
from operad.benchmark import sensitivity, regression_check

# How much does a small prompt perturbation move the metric?
sens = await sensitivity(agent, ds, perturbations=PERTURB_SET, metric=ExactMatch())

# Did the new version regress against the prior baseline?
report = regression_check(prev=baseline_eval, curr=current_eval, threshold=0.02)
assert not report.regressed
```

## How to extend

| What                      | Where                                                                          |
| ------------------------- | ------------------------------------------------------------------------------ |
| A new dataset format      | Yield `Entry`s; the rest is automatic.                                         |
| A new aggregation         | `aggregated.py` — extend the `Reducer` enum or pass a callable.                |
| A new perturbation suite  | Anywhere — pass to `sensitivity(perturbations=...)`.                           |
| Custom report fields      | Subclass `EvalReport`; the harness is structural.                              |

## Related

- [`../metrics/`](../metrics/README.md) — what `evaluate` calls.
- [`../data/`](../data/README.md) — `random_split(ds, [0.8, 0.2])` for
  train/val.
- [`../train/`](../train/README.md) — `Trainer.evaluate(test_ds)`
  delegates here.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §9 — full
  benchmark surface.
