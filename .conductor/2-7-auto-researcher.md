# 2 · 7 — `algorithms/auto_research.py` — AutoResearcher composition

**Addresses.** A1 (VISION §7 north-star #2 — autonomous research loop
assembled from existing leaves).

**Depends on.** 1-1-restructure.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §7 (north-star #2: autonomous research).
- `operad/algorithms/self_refine.py`, `operad/algorithms/best_of_n.py` —
  the two closest existing patterns.
- `operad/agents/reasoning/components/`: `planner.py`, `retriever.py`,
  `reasoner.py`, `critic.py`, `reflector.py` — the leaves this
  algorithm composes.
- `operad/agents/reasoning/schemas.py` — `Task`, `Answer`, `Query`,
  `Hits`, `Reflection`, `ReflectionInput`.
- `operad/agents/reasoning/react.py` — the shape of an existing multi-
  stage reasoning composition (for convention comparison).

---

## Proposal

Assemble an opinionated research loop from existing building blocks:
`Planner` produces a plan → `Retriever` fetches supporting hits →
`Reasoner` drafts an answer over those hits → `Critic` verifies the
answer's claims → `Reflector` decides whether to iterate. Wrap the loop
in `BestOfN` so the caller can pick the best candidate across N
attempts under a supplied metric.

### API

```python
# operad/algorithms/auto_research.py

from typing import Generic
from ..agents.reasoning.components import (
    Planner, Retriever, Reasoner, Critic, Reflector,
)
from ..agents.reasoning.schemas import Task, Answer
from ..core.agent import Agent
from ..metrics.base import Metric


class AutoResearcher(Generic[...]):
    """Planner → Retriever → Reasoner → Critic → Reflector loop,
    wrapped in BestOfN under a metric.

    Uses the `run(x)` pattern rather than `__call__(x)`, matching
    existing algorithms (SelfRefine, VerifierLoop). The loop is
    deterministic w.r.t. seeds given to each leaf's Configuration.
    """

    def __init__(
        self,
        *,
        planner: Planner,
        retriever: Retriever,
        reasoner: Reasoner,
        critic: Critic,
        reflector: Reflector,
        metric: Metric,
        n: int = 3,
        max_iter: int = 2,
    ) -> None:
        ...

    async def run(self, x: Task) -> Answer: ...
```

### Algorithm sketch

```
for attempt in range(n):
    plan   = await self.planner(x)                     # Task -> Plan
    hits   = await self.retriever(Query(plan.query))   # Query -> Hits
    draft  = await self.reasoner(ReasonerInput(task=x, hits=hits))
    verdict= await self.critic(draft)                  # Answer -> Verdict
    for _ in range(max_iter):
        r = await self.reflector(ReflectionInput(...))
        if not r.needs_revision:
            break
        draft = await self.reasoner(... incorporate r.suggested_revision ...)
        verdict = await self.critic(draft)
    candidates.append((draft, verdict))

# Pick the best candidate under the metric.
return max(candidates, key=lambda pair: await metric.score(pair[0], ...))
```

The exact wiring matches `BestOfN`'s contract from `algorithms/
best_of_n.py` (re-use it internally rather than re-implement the
selection loop). Each leaf is invoked through the standard `(await
leaf(x)).response` envelope — consistent with the rest of `algorithms/`.

### Why `algorithms/` not `agents/reasoning/`

Per `CLAUDE.md`: loop-with-metric-feedback whose natural API is not
`__call__(x)` → algorithm. `AutoResearcher` has a loop and takes a
metric in its constructor. The API is `run(task)`. Home is
`operad/algorithms/auto_research.py`.

### Re-export

```python
# operad/algorithms/__init__.py
from .auto_research import AutoResearcher
__all__ = [..., "AutoResearcher"]
```

The top-level `operad.__init__` does **not** promote
`AutoResearcher` — it's reachable at
`operad.algorithms.AutoResearcher` (per 1-1 stratification cap).

### No missing-marker removal needed

The original plan mentioned removing `TODO_AUTORESEARCHER` from
`missing.py`. There is no `missing.py` in the current tree (grep
confirms: no `TODO_AUTORESEARCHER` anywhere). Skip that step; the only
deliverable is the new file + re-export.

---

## Required tests

`tests/test_auto_researcher.py` (new):

1. **Offline run.** Build each leaf as a `FakeLeaf` that returns a
   fixed typed response. `AutoResearcher` assembled with those fakes
   plus a deterministic `Metric`. `await researcher.run(Task(
   goal="..."))` returns an `Answer` whose fields match the fake
   reasoner's output.
2. **`n=3` actually produces 3 candidates.** Assert the planner,
   retriever, reasoner, critic were each called 3× (stub leaves
   count invocations).
3. **Best-candidate selection.** Metric returns `0.1, 0.9, 0.2` for
   three candidates; the returned answer is the middle one (the
   highest scorer).
4. **max_iter guard.** `max_iter=0` disables the inner reflection
   loop; reflector is never called.
5. **Graph shape.** If AutoResearcher participates in any
   `AgentGraph` (it doesn't — it's an algorithm, not an Agent), no
   graph call. Smoke test: `AutoResearcher(...)` constructs with
   valid kwargs and raises `TypeError` with clear error if any leaf
   is missing.

All tests offline; no cassettes needed (FakeLeaf covers every stage).

---

## Scope

**New files.**
- `operad/algorithms/auto_research.py`
- `tests/test_auto_researcher.py`

**Edited files.**
- `operad/algorithms/__init__.py` — re-export `AutoResearcher`.

**Must NOT touch.**
- `operad/agents/reasoning/components/` — use the leaves as imported
  types; do not modify their schemas or prompts.
- Any other `operad/algorithms/` file beyond the `__init__.py`
  re-export line.
- `operad/core/`.
- Any runtime/metrics/utils file.

---

## Acceptance

- `uv run pytest tests/test_auto_researcher.py` green.
- `uv run pytest tests/` green.
- `from operad.algorithms import AutoResearcher` works.
- `AutoResearcher` does NOT appear in `operad.__all__` (stratified).

---

## Watch-outs

- **Component return types.** Each leaf returns an `OperadOutput[T]`
  envelope. Always unwrap via `.response` (like every other algorithm
  in the package) — never use the raw envelope as an input.
- **`BestOfN` re-use vs in-line loop.** Prefer re-using `BestOfN`
  internally (constructor takes a generator callable and a metric).
  Avoid a bespoke selection loop — keeps maintenance cost low and
  threads through `BestOfN`'s existing observer events.
- **Reasoner's input schema.** Today's `Reasoner` is generic on
  `In`/`Out`. `AutoResearcher` must pin it at construction time so
  the user supplies `reasoner: Reasoner[SomeInput, Answer]` with
  `SomeInput` carrying both task + hits. Document this in the brief
  docstring with a one-liner example.
- **Deterministic seeding under concurrency.** `BestOfN` may parallelise
  the N attempts. Each attempt's leaves must be built with distinct
  seeds (callers pass those in via each leaf's `Configuration.sampling.
  seed`) to avoid getting N identical candidates.
- **No global registry, no DI.** `AutoResearcher.__init__` takes explicit
  keyword-only arguments for every stage. Callers compose the
  instance. Keeps the algorithm introspectable by grep.
- **Metric for selection vs verifier.** `Critic` is the per-answer
  verifier (binary or graded verdict); `metric: Metric` is the
  selection scorer across N candidates. These are distinct; don't
  fold them. Document with a single sentence in the class docstring.
