# 4 · 3 — `CostObserver` wired to the registry

**Addresses.** N-1 — `CostTracker` has an `on_event` method but is
never attached to the observer `registry`. Cost accumulation across a
run tree is manual today. See [`../ISSUES.md`](../ISSUES.md) Group B.

**Depends on.** Phase 0's `OperadOutput.backend` / `model` fields
(already landed) and Phase 0's canonical `operad/runtime/cost.py`
(already landed). Nothing in Wave 4.

**Blocks.** 5-2 (dashboard) — cost panel reads the aggregator.

---

## Required reading

- `operad/runtime/cost.py` — `CostTracker`, `_CostEvent`, `PRICE_TABLE`.
  (`_CostEvent` is the transitional stub; we'll replace it with the
  real event in this brief.)
- `operad/runtime/observers/base.py` — `AgentEvent`, `Observer`
  Protocol, `registry`.
- `operad/core/agent.py` — where end events fire on invoke (look at
  `_build_envelope` + the `end` emission in `invoke` and `stream`).
- `operad/core/output.py` — the envelope now carries `backend`,
  `model`, `prompt_tokens`, `completion_tokens`.
- `tests/metrics/test_cost.py` — existing coverage for `cost_estimate`
  and `CostTracker`. Style to match.

---

## Goal

Replace the `_CostEvent` stub-based flow with a proper `Observer` that
reads `backend`, `model`, `prompt_tokens`, `completion_tokens` directly
off `AgentEvent.output` on `kind == "end"` and accumulates by
`run_id`. Keep `CostTracker` as the in-memory aggregator; the new
class is the glue that connects it to the live observer bus.

## Scope

### New class: `CostObserver` in `operad/runtime/cost.py`

```python
@dataclass
class CostObserver:
    """Observer that accumulates token + USD spend per run_id.

    Delegates the math to a `CostTracker`; exposes `totals()` for
    read-through. Register with `observers.registry.register(obs)`.
    """

    tracker: CostTracker = field(default_factory=CostTracker)
    pricing: dict[str, Pricing] | None = None  # overrides PRICE_TABLE

    async def on_event(self, event: Any) -> None:
        # Only end events carry a populated OperadOutput envelope.
        kind = getattr(event, "kind", None)
        if kind != "end":
            return
        out = getattr(event, "output", None)
        if out is None:
            return
        p = out.prompt_tokens or 0
        c = out.completion_tokens or 0
        key = f"{out.backend or 'unknown'}:{out.model or 'unknown'}"
        rate = _lookup_rate(self.pricing, key)
        cost = (p * rate.prompt_per_1k + c * rate.completion_per_1k) / 1000.0
        bucket = self.tracker._totals[out.run_id]
        bucket["prompt_tokens"] += p
        bucket["completion_tokens"] += c
        bucket["cost_usd"] += cost

    def totals(self) -> dict[str, dict[str, float]]:
        return self.tracker.totals()
```

### Deprecate `_CostEvent`

Keep it for one release cycle (tests still import it from
`operad.metrics.cost`). Add a `DeprecationWarning` in its
`__post_init__` (or a `__getattr__` hook on the module) directing
users to `CostObserver`. Remove it in Wave 5.

### Wire into `operad.tracing.watch`

Update `operad/tracing.py` so that `watch(cost=True)` (default `False`)
registers a `CostObserver` alongside the other observers.

### Public export

Add `CostObserver` to `operad/runtime/cost.py::__all__` and re-export
from `operad.runtime`'s `__init__.py`. No change to
`operad/metrics/cost.py` (it stays a thin shim).

---

## Verification

- Unit test: construct a `CostObserver`, build a fake `AgentEvent`
  with `kind="end"` and an envelope carrying known `backend`, `model`,
  `prompt_tokens`, `completion_tokens`. After one `on_event`, assert
  `totals()` shows the correct token and USD sums.
- Unit test: `kind != "end"` (start, chunk, error, algorithm events
  from brief 4-1) are ignored — `totals()` stays empty.
- Unit test: unknown `backend:model` → cost 0.0, tokens still counted.
- Integration test with a `FakeLeaf` that returns a canned envelope:
  attach `CostObserver` to the registry, invoke, assert totals. Unregister
  at teardown.
- `scripts/verify.sh` green.

---

## Out of scope

- Pricing accuracy for every hosted backend. Ship the current
  `PRICE_TABLE` as-is; add a handful of commonly-requested rows only
  if trivial. Users extend via `pricing=` kwarg.
- Real tokenisation. Keep the `len(text) // 4` fallback in
  `_default_tokenizer` for callers that use it elsewhere; the new
  observer relies on the provider-supplied token counts on the
  envelope.
- Dashboard rendering — brief 5-2.
- Per-algorithm cost attribution (cost per `GenerationEvent`). Could
  layer in Wave 5 if needed; not in scope here.

---

## Design notes

- Do not introduce a second registry or queue. Plug into the existing
  `ObserverRegistry`.
- Keep `CostObserver` small — one async method, one tracker instance,
  pass-through `totals()`. If users want subscription, they compose
  it with a notifier themselves.
- Compatible with brief 4-1: `AlgorithmEvent`s do not carry
  `output`, so `on_event` early-returns. No interaction.
