# 4 · 2 — `SlotRegistry.occupancy()` public API

**Addresses.** M-1 — SlotRegistry has no public way to read live
concurrency / RPM / TPM. See [`../ISSUES.md`](../ISSUES.md) Group B.

**Depends on.** Nothing in Wave 4. Runs in parallel with 4-1 / 4-3.

**Blocks.** 5-2 (dashboard) — the dashboard polls this to render the
slot panel.

---

## Required reading

- `operad/runtime/slots.py` — the whole file. Study `SlidingCounter`
  (window-based RPM/TPM) and `SlotRegistry` (per-(backend, host)
  semaphore + counters). Note `SlidingCounter.current(now)` already
  returns the used value — we just don't surface it.
- `operad/runtime/__init__.py` — public runtime symbols.
- `tests/runtime/test_slots.py` — existing patterns.

---

## Goal

Expose one public method on `SlotRegistry` that returns a snapshot of
occupancy across every endpoint, plus a typed `SlotOccupancy`
dataclass for consumers.

## Scope

### New types in `operad/runtime/slots.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SlotOccupancy:
    """Live utilisation for one (backend, host) key."""
    backend: str
    host: str
    concurrency_used: int
    concurrency_cap: int | None         # None = unbounded
    rpm_used: int
    rpm_cap: int | None
    tpm_used: int
    tpm_cap: int | None
```

### New method on `SlotRegistry`

```python
def occupancy(self) -> list[SlotOccupancy]:
    """Return a snapshot across all registered (backend, host) keys.

    Reads are atomic per key (one lock acquire per key); the list is
    built best-effort over the keys known at call time. Counters use
    the sliding-window `current(now)` value, so RPM/TPM reflect the
    last minute up to `now = time.monotonic()`.
    """
```

### Export

Add `SlotOccupancy` to `operad/runtime/__init__.py`'s `__all__` so
downstream code can `from operad.runtime import SlotOccupancy`.

---

## Verification

- Set limits on two endpoints via `operad.set_limit(...)`, simulate
  load (acquire a couple of slots, record fake request / token
  settles), call `occupancy()`, and assert:
  - length == number of registered keys
  - `concurrency_used` matches the number of outstanding acquires
  - `rpm_used`, `tpm_used` reflect the recorded settles
  - caps pass through from the underlying limiter
- Cover the "no cap" case (`concurrency_cap` → `None` when bound is
  infinity).
- Concurrency safety: call `occupancy()` while another task holds a
  slot; the snapshot should not deadlock.
- `scripts/verify.sh` green.

---

## Out of scope

- Any dashboard or UI code. That's brief 5-2.
- Emitting slot events on the observer bus. If someone wants live
  slot telemetry, a future `SlotObserver` can poll `occupancy()` on a
  timer and fire `AlgorithmEvent(kind="algo_...")`-style pings — but
  that's not this brief. Expose the read API; let consumers poll.
- Retroactive per-key history. `occupancy()` is a snapshot, not a
  time series.

---

## Design notes

- Keep the dataclass frozen-slotted so downstream code can hash or
  compare snapshots cheaply.
- Do not add a `dict`-returning helper; users who want that do
  `{(o.backend, o.host): o for o in registry.occupancy()}`.
- Leave the private `SlidingCounter.current(now)` call signature
  alone; call it internally from `occupancy()`.
