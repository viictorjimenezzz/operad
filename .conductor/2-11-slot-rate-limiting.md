# 2 · 11 — Slot rate limiting: TPM / RPM per endpoint

**Addresses.** S1 (extend `SlotRegistry` beyond concurrency to enforce
tokens-per-minute and requests-per-minute per endpoint).

**Depends on.** 1-1-restructure.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §7 (safety: protect shared endpoints
  from overload).
- `operad/runtime/slots.py` — `SlotRegistry`, `set_limit`, `acquire`.
  The call site is `operad.core.agent.Agent.forward` (default-forward
  path), inside `async with acquire(self.config)`.
- `operad/core/config.py` — `Configuration`, keyed by `(backend, host)`.

---

## Proposal

Today, `SlotRegistry` enforces **concurrency** only — a per-endpoint
`asyncio.Semaphore` bounds how many forwards run at once. For
rate-limited hosted providers (OpenAI, Anthropic, Gemini), concurrency
is the wrong knob: you can have low parallelism and still blow past a
TPM budget. Extend `set_limit` to accept three orthogonal caps:

- `concurrency` — existing semaphore bound.
- `rpm` — requests per minute (sliding window).
- `tpm` — tokens per minute (sliding window; tokens = prompt +
  completion, charged at forward completion).

All three stack. `acquire(cfg)` must hold all three gates
simultaneously before letting the call through.

### Public API

```python
# operad/runtime/slots.py

def set_limit(
    *,
    backend: Backend,
    host: str | None = None,
    concurrency: int | None = None,
    rpm: int | None = None,
    tpm: int | None = None,
) -> None:
    """Configure per-endpoint caps.

    Any omitted field leaves the current value unchanged. `concurrency`
    may only be set before the first acquire on that endpoint (existing
    rule). `rpm` and `tpm` may be updated at any time — they're
    sliding-window counters that just change their budget.
    """
```

Keep the positional-less keyword-only style.

### Acquire shape

```python
@asynccontextmanager
async def acquire(cfg: Configuration) -> AsyncIterator["SlotToken"]:
    """Block until all three gates allow the call.

    Yields a `SlotToken` the caller `settle()`s when the call
    completes — used to charge TPM after tokens are known.
    """
```

`SlotToken` is a small context object:

```python
class SlotToken:
    def settle(self, *, tokens: int) -> None:
        """Record the actual token cost of the completed request."""
```

The concurrency semaphore is acquired first (unchanged behaviour).
The RPM gate is acquired next: if the sliding window is full, the
coroutine awaits a monotonic-clock deadline. The TPM gate is acquired
last, **provisionally** — we don't know the token count yet, so we
reserve the per-call estimate (from `Configuration.sampling.max_tokens`
plus a heuristic prompt-length cap) and reconcile on `token.settle()`.

### Sliding-window implementation

```python
class SlidingCounter:
    """Monotonic-clock sliding window over the last 60s."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._events: collections.deque[tuple[float, int]] = collections.deque()

    def _expire(self, now: float) -> None:
        while self._events and self._events[0][0] < now - 60.0:
            self._events.popleft()

    def current(self, now: float) -> int:
        self._expire(now)
        return sum(n for _, n in self._events)

    async def acquire(self, amount: int = 1) -> None:
        """Block until `current + amount <= limit`."""

    def charge(self, amount: int) -> None:
        """Record `amount` at the current monotonic time."""
```

One `SlidingCounter` per endpoint-per-kind (rpm, tpm). Clock source:
`asyncio.get_running_loop().time()` for async-friendly sleep; the
loop clock is monotonic and consistent with `asyncio.sleep`.

### Integration with `Agent.forward`

Current call site (in agent.py post-1-1 envelope):

```python
async with acquire(self.config):
    result = await strands_call(...)
```

Becomes:

```python
async with acquire(self.config) as slot:
    result = await strands_call(...)
    slot.settle(tokens=result.prompt_tokens + result.completion_tokens)
```

Semantic: the concurrency slot is released as the `async with` exits.
TPM is charged the actual-tokens amount at `settle`. RPM is charged
1 at acquire time.

`slot.settle` is idempotent (first call wins) — guards against double-
billing on retries.

### Default behaviour

When neither `rpm` nor `tpm` is set (the common case), the gates
short-circuit and add no overhead. The concurrency semaphore behaves
exactly as today. Opt-in ergonomic:

```python
operad.set_limit(backend="openai", rpm=500, tpm=90_000)
```

### Blocking vs raising

The Wave 1 spec said "blocking vs raising is a caller-chosen policy
(default: await)." Keep the default: await until the window clears.
No new enum. If we ever need the raising variant, add it as a kwarg
in a future brief.

---

## Required tests

`tests/test_slots_rate_limit.py` (new):

1. **RPM blocks second request.** Set `rpm=2`; fire three acquires in
   parallel with a monotonic-clock stub; third one waits until the
   window has space.
2. **TPM charges on settle.** Set `tpm=1000`; acquire, settle with
   `tokens=900`; a second acquire that would reserve 200 waits for
   window rollover.
3. **RPM + TPM stack.** Set both; an acquire that would fit TPM but
   exceed RPM still blocks on RPM. And vice versa.
4. **Concurrency unchanged.** Setting `concurrency=3` without RPM/TPM
   behaves byte-identically to today's `set_limit(limit=3)`.
5. **Default zero overhead.** Micro-benchmark: 1000 acquires on an
   endpoint with no RPM/TPM set take < 50ms (well below any threshold
   we'd want to measure; presented as a guard against a gate that
   spins even when unused).
6. **Settle idempotence.** Calling `slot.settle(tokens=100)` twice
   charges the window only once.
7. **Reset.** `registry.reset()` clears all counters and semaphores.
8. **Unknown endpoint inherits default.** An acquire against an
   endpoint with no explicit limits uses `default` concurrency, no
   RPM/TPM.
9. **`set_limit` partial update.** After `set_limit(backend=...,
   rpm=100)`, the TPM limit stays unset. A subsequent
   `set_limit(backend=..., tpm=5000)` leaves RPM at 100.

Use `asyncio.get_event_loop().time()`-stubbed tests via
`monkeypatch.setattr(time, "monotonic", fake_clock)` style, or build
the counter to accept a clock callable parameter to keep tests
deterministic.

---

## Scope

**New files.**
- `tests/test_slots_rate_limit.py`.

**Edited files.**
- `operad/runtime/slots.py` — extend the registry, add `SlidingCounter`,
  rework `acquire` to yield a `SlotToken`.
- `operad/core/agent.py` — **ONE** edit: the `async with acquire(...)` 
  call site now binds the yielded `slot` and calls `slot.settle(...)`
  after the strands call. This is the only change outside `slots.py`.

**Must NOT touch.**
- Other files in `operad/runtime/` beyond `slots.py`.
- `operad/core/config.py` — no new Configuration fields (RPM/TPM are
  registry-level, not per-agent).
- `operad/core/models.py`, `operad/agents/`, `operad/algorithms/`,
  `operad/metrics/`, `operad/utils/`.

**Shared file coordination with 2-1.** `operad/core/agent.py` is owned
by 2-1 in Wave 2. The slot-settle edit is exactly one call site and
~3 LOC. If 2-1 lands first, apply the change cleanly. If this PR
lands first, 2-1 must preserve the `slot.settle(...)` call when it
reshapes `forward`. Coordinate via the conductor task list if
conflict looms.

---

## Acceptance

- `uv run pytest tests/test_slots_rate_limit.py` green.
- `uv run pytest tests/` green.
- `operad.set_limit(backend="openai", rpm=500, tpm=90_000)` works with
  or without the OpenAI backend actually being installed (purely in-
  memory registry).
- Existing integration tests that rely on per-endpoint concurrency
  (`OPERAD_INTEGRATION=llamacpp …`) continue to work unchanged.

---

## Watch-outs

- **Loop affinity.** `asyncio.Semaphore` is single-loop-bound. The
  sliding counter shares that constraint — it uses `loop.time()` and
  `loop.create_future()`. Multi-loop test harnesses must call
  `registry.reset()` between loops.
- **Token estimate before settle.** Until the call returns, we don't
  know the real token count. The provisional reserve is
  `cfg.sampling.max_tokens + estimated_prompt_tokens`. Overshoot is
  safe (leaves some budget unused); undershoot is dangerous
  (over-admits). Err on the high side; the heuristic is "max_tokens +
  2 × len(prompt_chars) / 4".
- **Settle on error.** If the forward raises before tokens are known,
  `slot.settle(...)` still must be called (with `tokens=0`) so the
  provisional reserve releases. Wrap the strands call in a `try /
  finally` at the call site.
- **Retries double-count.** The strands retry path (inside the
  default-forward leaf) produces one final token count for the
  successful attempt. Charge once, at `settle`. Don't charge on each
  intermediate retry — the sliding window must not double-account.
- **`rpm=0` / `tpm=0`.** Treat as "unlimited" (remove any existing
  gate). Reject negative numbers loudly.
- **Clock stubbing in tests.** The counter accepts a clock callable
  parameter (`time_fn: Callable[[], float] = time.monotonic`), so
  tests can pass a deterministic stepper without monkeypatching the
  module.
- **No new top-level exports.** `operad.set_limit` already exists
  (1-1's stratified re-export). The signature gains kwargs — same
  name, same import site, no `operad/__init__.py` edit needed.
