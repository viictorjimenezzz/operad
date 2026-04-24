# 1-1 — EvoGradient mutation attribution

**Wave.** 1. **Parallel with.** 1-{2..6}. **Unblocks.** 2-2.

## Context

`EvoGradient.step()` emits `AlgorithmEvent(kind="generation",
payload={gen_index, population_scores, survivor_indices, best_index})`.
It does *not* say which `Op` produced each survivor, so dashboards
can't show "AppendRule succeeded 3× this gen, SetTemperature 0×."
Adding that attribution is a ~one-line fix at the emission site,
but it unlocks wave-2 UI.

## Scope — in

### `operad/optim/evo.py`

- Track per-individual provenance: whenever `_mutate` clones +
  applies an `Op`, record `(individual_id, op_name)` in a small
  per-step buffer.
- Extend the `generation` payload with new keys:
  - `mutations: list[dict]` — one entry per individual, shape
    `{"individual_id": int, "op": str, "improved": bool}`.
    `improved` is `True` iff this individual's metric score is
    strictly above the median of the previous generation (or the
    seed on gen 0).
  - `op_success_counts: dict[str, int]` — aggregated per-op success
    count for this generation.
  - `op_attempt_counts: dict[str, int]` — aggregated per-op attempt
    count.
- Keep existing keys untouched (backward compat).

### `operad/runtime/events.py`

- Document the new payload keys in the `AlgorithmEvent` docstring
  (no schema enforcement — payload is `dict[str, Any]`).

### `tests/optim/test_evo.py` (extend)

- With a stubbed population of 4 members and 2 mutations
  (`AppendRule`, `SetTemperature`), run one generation and assert:
  - `payload["mutations"]` has 4 entries, each with a valid op name.
  - `payload["op_attempt_counts"]` sums to 4.
  - `payload["op_success_counts"][op] <= op_attempt_counts[op]` ∀ op.

## Scope — out

- Do **not** change `EvoGradient`'s selection logic. Attribution is
  read-only bookkeeping.
- Do not extend other optimizers (OPRO / APE) yet — their mutation
  model is different; we'll do them in a follow-up if it's useful.

## Dependencies

- None (purely within `operad/optim/evo.py`).

## Design notes

- **`improved` semantics.** Measure improvement against the *previous
  generation's median* score, not the seed. For gen 0, measure
  against the seed's score (since there's no prior gen). Document in
  the method.
- **Op identity.** Use `op.name` (the Pydantic field) as the key —
  matches `operad.utils.ops`.
- **Payload size.** `mutations` grows with population; for
  populations > 100, this may bloat the event. Add a soft cap
  (`max_mutation_entries: int = 200`) — beyond which we emit only
  aggregates. Document but default generously.

## Success criteria

- `uv run pytest tests/optim/test_evo.py -v` passes including the
  new assertions.
- `uv run ruff check operad/optim/evo.py` clean.
- Replaying an existing NDJSON trace without the new keys does not
  break downstream consumers (backward-compat check: load an old
  `test_cassettes/*.jsonl` that predates the change).
