# Phase 2 · Stream D — Metrics & dataset-level evaluation

**Goal.** Make the `Metric` protocol batch-aware, add cheap
deterministic scorers, ship a `RubricCritic` that wraps an LLM judge
as a metric, and ship an `evaluate(agent, dataset, metrics)` harness.

**Owner:** one agent.
**Depends on.** Stream C (cost metrics subscribe to observer events).
**Addresses:** B-2, C-6.

---

## Scope

### Files you will create
- `operad/metrics/contains.py` — `Contains` scorer.
- `operad/metrics/regex_match.py` — `RegexMatch` scorer.
- `operad/metrics/rouge.py` — `Rouge1` scorer (pure Python).
- `operad/metrics/rubric_critic.py` — LLM-judge-as-metric wrapper.
- `operad/metrics/cost.py` — observer-subscribed cost/token aggregator.
- `operad/eval.py` — `evaluate(...)` harness + `EvalReport`.
- `tests/test_metrics_contains.py`, `test_metrics_regex.py`,
  `test_metrics_rouge.py`, `test_rubric_critic.py`, `test_eval.py`.
- `examples/eval_loop.py`.

### Files you will edit
- `operad/metrics/base.py` — extend `Metric` protocol with
  `score_batch`.
- `operad/metrics/__init__.py` — re-exports.
- `operad/__init__.py` — re-exports.

### Files to leave alone
- Everything outside `operad/metrics/` and `operad/eval.py`.

---

## Design direction

### Extended `Metric` protocol

Keep backwards compat:

```python
@runtime_checkable
class Metric(Protocol):
    name: str
    async def score(self, predicted: BaseModel, expected: BaseModel) -> float: ...

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]:
        return [await self.score(p, e) for p, e in pairs]
```

The default implementation keeps existing metrics working untouched.
Subclasses that benefit from batching (e.g. `RubricCritic`) can
override for concurrency.

### `Contains`, `RegexMatch`, `Rouge1`

All dataclass-style, no deps. `Rouge1` is unigram overlap —
precision/recall/F1 — not the real rouge-score library. Keep the code
under 60 lines each.

Each metric is told *which field* of the output to score:

```python
@dataclass
class Contains:
    field: str
    name: str = "contains"

    async def score(self, predicted, expected) -> float:
        return 1.0 if str(getattr(expected, self.field)) in str(getattr(predicted, self.field)) else 0.0
```

### `RubricCritic`

Wraps an `Agent[Candidate[In, Out], Score]` (i.e. a `Critic`) as a
`Metric`. `.score()` returns `score.score`. Implement `score_batch`
with `asyncio.gather` so evaluation parallelises correctly against
the slot registry.

### `evaluate(...)`

```python
class EvalReport(BaseModel):
    rows: list[dict[str, Any]]
    summary: dict[str, float]

async def evaluate(
    agent: Agent[In, Out],
    dataset: list[tuple[In, Out]],
    metrics: list[Metric],
    *,
    concurrency: int = 4,
) -> EvalReport: ...
```

Behaviour:
- Require `agent._built is True`; raise `BuildError("not_built", ...)`
  otherwise. Don't silently auto-build.
- Run all inputs through `asyncio.gather` bounded by a local
  `asyncio.Semaphore(concurrency)` (separate from the slot registry,
  which bounds the *backend* not the *agent call*).
- For each metric, call `score_batch` on `(predicted, expected)` pairs.
- `rows` = list of `{"input": dumped, "expected": dumped, "predicted":
  dumped, <metric_name>: score}`.
- `summary` = per-metric mean (ignore NaNs).

### `cost.py`

Subscribes to `AgentEvent` via the observer registry. Accumulates
estimated tokens (prompt length in chars / 4 as a first cut) keyed by
`run_id`. Exposes `totals()` returning `{run_id: {prompt_tokens,
completion_tokens, cost_usd}}`. Cost table hard-coded per backend/model
for a small starter set.

This is a rough first cut — don't over-engineer. Real tokenisation and
real pricing come later.

---

## Tests

- `Contains`, `RegexMatch`, `Rouge1` — direct unit tests with
  hand-crafted Pydantic output objects.
- `RubricCritic` — with a FakeLeaf critic that returns a scripted
  `Score`, `.score()` returns the field value.
- `evaluate`:
  - FakeLeaf agent + `ExactMatch` over 3 rows → summary mean correct.
  - Agent not built → raises.
  - Concurrency bound respected (can spy with a semaphore leak test).
- `cost.py` — accumulates tokens across simulated observer events.

---

## Acceptance

- `uv run pytest tests/` green.
- `examples/eval_loop.py` runs a 5-row offline evaluation and prints
  an `EvalReport`.

---

## Watch-outs

- Do NOT pull heavy NLP deps (`rouge_score`, `nltk`, etc.). `Rouge1`
  is just overlap.
- Do NOT let `evaluate` auto-build the agent. Build is a caller
  responsibility.
- `score_batch` must remain an async method (LLM judges need it).
- `cost.py` subscribes via the global registry from Stream C —
  don't introduce a parallel bus.
