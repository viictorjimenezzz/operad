# 1-2 — Data layer: `DataLoader`, `random_split`

**Wave.** 1 (no prior-wave dependencies).
**Parallel with.** 1-1.
**Unblocks.** 4-3 (`Trainer`).

## Context

`Trainer.fit()` iterates over batched/shuffled/optionally-parallel
slices of a `Dataset`. `torch.utils.data` calls this primitive a
`DataLoader`. `operad.benchmark.Dataset` already exists as a typed
collection of `Entry[In, Out]` — we just need a loader and a
split helper.

Read `operad/benchmark/dataset.py` (current Dataset shape) and
`.context/NEXT_ITERATION.md` §12 before starting.

## Scope — in

- `operad/data/__init__.py` — re-exports `DataLoader`, `random_split`,
  `Batch`, and any samplers.
- `operad/data/loader.py`:
  - `class Batch(BaseModel, Generic[In, Out])` — carries
    `inputs: list[In]`, `expected: list[Out | None]`, `batch_id: str`,
    `hash_batch: str` (stable hash of inputs for cassette friendliness),
    `indices: list[int]`.
  - `class DataLoader(Generic[In, Out])`:
    - Constructor: `dataset, batch_size=1, shuffle=False,
      drop_last=False, num_workers=0, sampler: Sampler | None = None,
      seed: int | None = None, collate_fn=None`.
    - `__aiter__ / __anext__` — async iteration yielding `Batch` objects.
    - `__len__` — number of batches.
    - When `num_workers > 0`, dispatch batch construction through
      `operad.runtime.launchers.SandboxPool` (use `max_workers=num_workers`)
      to parallelize collate work; otherwise do it inline. This is a
      minor perf tweak, not a contract — most training runs will use
      `num_workers=0`.
    - `seed` makes shuffling deterministic; `DataLoader(ds, shuffle=True,
      seed=42)` must be reproducible.
  - `class Sampler(Protocol)`:
    - `__iter__(self) -> Iterator[int]` and `__len__(self) -> int`.
    - Shipped implementations: `SequentialSampler`, `RandomSampler`,
      `WeightedRandomSampler` (for curriculum-style weights).
- `operad/data/split.py`:
  - `def random_split(dataset: Dataset, fractions: list[float], *,
    seed: int | None = None) -> list[Dataset]`.
  - Validate fractions sum to 1.0 ± 1e-6, all positive.
  - Returns *new* `Dataset` instances with the same `name` + a
    version suffix (`name="trivia/train"` etc.) so
    `hash_dataset` remains stable across runs.
- `tests/data/__init__.py` — empty.
- `tests/data/test_loader.py`:
  - `DataLoader(ds, batch_size=4)` yields ceil(len/4) batches.
  - `drop_last=True` drops the partial final batch.
  - `shuffle=True, seed=42` gives the same order on re-iteration.
  - `shuffle=True` with different seeds gives different orders.
  - `num_workers=0` yields batches in sequential order; smoke-test
    `num_workers=2` also yields the right set (order irrelevant).
  - `Batch.hash_batch` is stable for equal inputs.
- `tests/data/test_split.py`:
  - `random_split(ds, [0.8, 0.2], seed=1)` gives deterministic halves.
  - No duplicate entries across splits.
  - Fractions < 1 or > 1 raise a clear error.

## Scope — out

- Do **not** modify `operad/benchmark/` (the existing `Dataset` must
  keep working unchanged).
- Do not integrate with `Trainer` here — that's 4-3.
- Do not add streaming / infinite datasets / remote shards. Finite
  in-memory only for this task.

## Dependencies

- `operad.benchmark.Dataset`, `operad.benchmark.Entry`.
- `operad.runtime.launchers.SandboxPool` (for optional `num_workers>0`).
- `operad.utils.hashing.hash_json` (for `hash_batch`).
- `pydantic.BaseModel`.

## Design notes

- `Batch` is a thin typed wrapper, not a deep clone of the dataset.
  `inputs` and `expected` are lists of pydantic instances; pass them
  by reference to downstream code.
- `batch_id` should be deterministic given `(dataset.hash_dataset,
  tuple(indices))`. Reuse `hash_json` on that tuple.
- `collate_fn` default = "pack into lists." Users may override to
  produce custom `Batch` subclasses (e.g., with padding, auxiliary
  metadata).
- Think about future compatibility with `Entry.metric_override` — a
  loader must preserve that metadata so `Trainer`'s evaluation can
  honor per-row metrics. Carry a parallel `metric_overrides: list[...]`
  on `Batch`.

## Success criteria

- `uv run pytest tests/data/ -v` passes offline.
- `uv run ruff check operad/data/` is clean.
- `from operad.data import DataLoader, random_split, Batch` works.
- `DataLoader(ds, batch_size=8, shuffle=True, seed=0)` produces
  reproducible batches.
- No changes to `operad/benchmark/`, `operad/core/`, or other
  pre-existing code.
