# Add stratified sampling to `operad/data/`

## Goal
`operad.data` ships `RandomSampler`, `SequentialSampler`, `WeightedRandomSampler`, `UncertaintySampler`, plus `random_split` — all uniform-random. Class-imbalanced supervised tasks (classification, safety labels, retrieval relevance) need `StratifiedSampler` and `stratified_split`. Add them.

## Context
- `operad/data/` — the existing samplers and `random_split`.
- A `Dataset` is a sequence of `Entry(input, expected_output)`. Stratification needs a key extractor (callable or a dotted path on `expected_output`).

## Scope

**In scope:**
- `operad/data/samplers.py` — `StratifiedSampler(dataset, key, batch_size=None, shuffle=True, seed=None)`. Yield indices such that each class's frequency matches the dataset's class distribution per batch (or as close as the batch size permits).
- `operad/data/splits.py` (or wherever `random_split` lives) — `stratified_split(dataset, fractions, key, seed)`. Same per-class proportions in each split.
- `operad/data/__init__.py` — re-export.
- Tests under `tests/data/` that build a synthetic 80/20 imbalanced dataset and assert: (a) every batch in `StratifiedSampler` has the expected class ratio (within rounding), (b) `stratified_split` preserves ratios in both halves.

**Out of scope:**
- Changing `DataLoader` itself.
- Multi-key (compound) stratification — single key is enough for v1; document the limitation.
- The `UncertaintySampler` (it's its own beast).

**Owned by sibling iter-1 tasks — do not modify:**
- `operad/optim/*`, `operad/train/*`, `operad/runtime/*`, `operad/utils/*`, `operad/core/*`, `examples/`.

## Implementation hints
- The `key` argument should accept either a callable `(Entry) -> Hashable` or a dotted path string evaluated against `entry.expected_output` (`"label"`, `"category.name"`).
- Reuse `numpy.random.default_rng` if numpy is already a transitive dep; otherwise stick to `random.Random(seed)` for hermeticity.
- For very rare classes (count < `batch_size`), fall back to oversampling within the batch and emit a `UserWarning` once.
- Look at how `random_split` is implemented and mirror its API shape exactly — same return tuple, same seed handling.

## Acceptance
- Stratification tests pass.
- Existing samplers/split tests pass.
- New entries are exported from `operad.data` and listed in `INVENTORY.md` §21 (data subsection).
