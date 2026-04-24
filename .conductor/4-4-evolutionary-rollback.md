# 4 · 4 — `Evolutionary` clone-before-mutate rollback

**Addresses.** H-2 — `Evolutionary._mutate` applies an `Op` in place
and has no rollback if a later `abuild()` fails. See
[`../ISSUES.md`](../ISSUES.md) Group D.

**Depends on.** Phase 0's F-2 fix (already landed — required so the
cloned mutated agent actually rebuilds correctly).

**Blocks.** 5-1 (`agent.auto_tune()` wraps Evolutionary and must have
safe mutation semantics).

---

## Required reading

- `operad/algorithms/evolutionary.py` — the whole file, especially
  `_mutate` (line ~55) and `run` (line ~60).
- `operad/utils/ops.py` — every `Op` subclass (`AppendRule`,
  `EditTask`, `SetRole`, etc.). Study what "apply in place" means and
  what state each op touches.
- `operad/core/agent.py` — `clone()` (line ~270). We already know
  cloning after build is safe post-Phase-0.
- `examples/evolutionary_demo.py` — shows the intended calling
  shape.
- `tests/algorithms/test_evolutionary.py` — existing test patterns.

---

## Goal

Two deliverables:

1. **Clone-before-mutate in `Evolutionary`.** Every mutation is
   applied to a fresh clone so the original `seed` and prior survivors
   are never touched. If the resulting agent's `abuild()` or
   evaluation fails, the half-mutated copy is dropped and the
   individual is replaced with a re-cloned survivor.
2. **`Op.undo()` protocol on `operad/utils/ops.py`.** Every op
   records the pre-state so `op.undo(agent)` restores it. Enables
   fine-grained rewind inside higher-level algorithms and makes
   `AgentDiff` invertible for free.

## Scope

### `Op.undo(agent)` protocol

Today each op has `apply(agent)`. Add:

```python
class Op(Protocol):
    path: str
    def apply(self, agent: Agent[Any, Any]) -> None: ...
    def undo(self, agent: Agent[Any, Any]) -> None: ...
```

Every existing op implements it. Common pattern:

```python
@dataclass
class AppendRule(Op):
    path: str
    rule: str
    _prev: list[str] | None = None  # captured at apply-time

    def apply(self, agent: Agent[Any, Any]) -> None:
        target = _walk_to_path(agent, self.path)
        self._prev = list(target.rules)
        target.rules = target.rules + [self.rule]

    def undo(self, agent: Agent[Any, Any]) -> None:
        if self._prev is None:
            raise RuntimeError("undo() called before apply()")
        target = _walk_to_path(agent, self.path)
        target.rules = self._prev
```

Do the same for `EditTask`, `SetRole`, any `SetTemperature`/
`SetMaxTokens`-shaped ops, etc. The pattern is "snapshot the field
on `apply`, restore on `undo`". Ops mutate structure (attach/detach
child Agents) capture the full `_children` before/after if needed.

### `Evolutionary.run` rollback

Current flow (post-Phase-0):

```python
population = [self._mutate(self.seed.clone()) for _ in range(self.population_size)]
for _ in range(self.generations):
    await asyncio.gather(*(a.abuild() for a in population))
    reports = await asyncio.gather(*(evaluate(...)))
    ...
```

Replace with a helper that guarantees rollback on build failure:

```python
async def _attempt_mutate_and_build(
    self, parent: Agent[In, Out]
) -> Agent[In, Out] | None:
    """Clone parent, apply a random mutation, attempt build.
    Returns None if build fails; the parent's clone is left untouched."""
    candidate = parent.clone()
    op = self._rng.choice(self.mutations)
    # reset op's captured undo state before apply:
    op = copy.deepcopy(op)
    op.apply(candidate)
    try:
        await candidate.abuild()
        return candidate
    except BuildError:
        op.undo(candidate)  # restore for future reuse of op/candidate
        return None
```

In `run()`, if `_attempt_mutate_and_build` returns `None` up to
`max_retries=3` times for one slot, fall back to re-cloning the
survivor with no mutation (log a warning). Never put a half-mutated
agent in the population.

Also wire into brief 4-1's event schema: before each mutation emit
`AlgorithmEvent(kind="iteration", payload={"phase": "mutation", ...})`,
after each generation the existing `generation` event. These hooks
let the dashboard show mutation attempts per individual.

### Backwards compat

`_mutate` (the old helper) stays as a thin wrapper that calls
`_attempt_mutate_and_build` and raises on None — so existing callers
keep working. Add a deprecation docstring pointing at the new helper.

---

## Verification

- `tests/algorithms/test_evolutionary.py` gains a test where one
  mutation deliberately produces a build-failing agent (e.g. a `Set`
  op that makes the output type incompatible with a downstream child
  in a Pipeline seed). Assert:
  - The generation completes.
  - The population size is preserved.
  - No agent in the final population has the bad state.
  - The seed is not mutated (`seed.state() == seed_state_before`).
- `tests/utils/test_ops.py` (new file if needed): for each op,
  `apply` then `undo` brings state back to bitwise equality with
  `state_before`.
- Existing `examples/evolutionary_demo.py --offline` still runs.
- `scripts/verify.sh` green.

---

## Out of scope

- Persisting the mutation history beyond in-memory ops. If a user
  wants mutation lineage, they can capture `AgentDiff` objects
  separately.
- Parallel mutation across threads. `run()` stays single-threaded with
  async overlap via `gather`; no threading.
- Sentinel proxy (brief 4-5) is an independent build-time correctness
  layer. This brief just needs builds to fail cleanly when
  incompatible — it doesn't rely on the proxy for detection.

---

## Design notes

- Use `copy.deepcopy(op)` before apply so each op instance carries
  its own `_prev` snapshot. Alternative: have `apply` return a
  `Snapshot` object and `undo(agent, snapshot)`. Either works; pick
  the lighter-weight one for ergonomics.
- Do not introduce a new `OpTransaction` context manager. The
  internal `_attempt_mutate_and_build` helper is enough.
- Keep `run()` single-method; don't split into a class per generation.
