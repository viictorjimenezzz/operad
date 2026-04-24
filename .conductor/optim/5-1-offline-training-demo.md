# 5-1 — End-to-end offline training demo

**Wave.** 5 (depends on everything in waves 1-4).
**Parallel with.** 5-2, 5-3, 5-4, 5-5.

## Context

The library's credibility hinges on a running demo that shows an
agent visibly improving across epochs under a deterministic offline
test. This task delivers that demo: a small synthetic task, a
FakeLeaf-backed pipeline, and a training run whose result
`hash_content` differs from the seed.

Read `examples/evolutionary_demo.py` for the existing offline-demo
pattern we should match, and `.context/NEXT_ITERATION.md` §17-18.

## Scope — in

### `examples/train_demo.py`

- A small self-contained script runnable with
  `uv run python examples/train_demo.py --offline`.
- Construct a toy scenario:
  - `In`/`Out` schemas simple enough to embed in the file.
  - A `FakeLeaf`-style agent whose `forward` deterministically maps
    `In → Out` based on its declared `role` / `task`. The idea: the
    "better" the role/task string, the higher the metric score on a
    small held-out dataset. You can simulate this with a keyword-
    matching metric (e.g., "emit the word 'concise' → +1 to score").
  - A deterministic `FakeCritic` / stubbed rewriter / stubbed
    backprop agent that mimic realistic textual gradients.
- Full training run:
  1. Build an unoptimized agent with weak role/task strings.
  2. Evaluate → print seed score.
  3. Instantiate `TextualGradientDescent` + `StepLR` + `CriticLoss`.
  4. Run `Trainer.fit(loader, val, epochs=5)`.
  5. Print `TrainingReport`: per-epoch loss, metric, LR, hash_content.
  6. Assert final `hash_content` != seed `hash_content`.
  7. Assert final val metric > seed val metric.
- CLI flags:
  - `--offline` — use FakeLeaf + stubbed rewriters (default; no LLM).
  - `--backend llamacpp --host 127.0.0.1:8080 --model qwen2.5-7b`
    — run with a real LLM for a live demo.
- Rich output: use the `rich` printing style from `demo.py` for
  tables, epoch-by-epoch reports, hash diffs.

### `scripts/verify.sh`

- Add a line that runs `examples/train_demo.py --offline` as part
  of the offline verification suite (same pattern as existing
  offline examples).
- Confirm the script exits 0.

### Documentation

- Optional: add a screenshot or a snippet of the output to the demo's
  docstring / commented header.

## Scope — out

- Do **not** implement new optimizers, losses, or callbacks. Only
  compose what already exists in `operad.optim` + `operad.train`.
- Do not introduce new metrics beyond `ExactMatch` / `Contains` /
  `RubricCritic`-style wrappers.
- Do not mutate `demo.py`. The main demo stays as-is.

## Dependencies

- All of waves 1-4.
- Existing: `operad.Agent`, `operad.agents.pipeline.Pipeline`,
  `operad.benchmark.Dataset`, `operad.metrics.ExactMatch`,
  `rich` (optional extra — keep this demo runnable without it).

## Design notes

- **Determinism is the product.** The `--offline` path must produce
  identical output on every run (tests can't rely on wall-clock).
  Seed every RNG; stub every LLM. Assert exact expected hashes at
  the end (commit them after the first clean run).
- **Small dataset.** 4-8 examples — enough to show training, quick
  enough for CI.
- **Offline optimizer substitution.** `TextualGradientDescent` needs
  a `RewriteAgent`; provide a local `FakeTextRewriter(Agent)` that
  overrides `forward` to return a deterministic edit. Do this in
  `examples/_train_helpers.py` (new file) so 5-5 can reuse it for
  the cassette-replay test.
- **Runnable as-is.** The entire demo should run under 30 seconds
  offline. No LLM, no network. This is a *verification* demo, not a
  performance benchmark.
- **Display.** Use `rich.table.Table` for per-epoch progress with
  columns: epoch, loss, metric, lr, hash_content[:12], delta.

## Success criteria

- `uv run python examples/train_demo.py --offline` exits 0.
- Final `hash_content` != seed `hash_content`.
- Val metric monotonically non-decreasing (with small tolerance).
- `bash scripts/verify.sh` passes with the new demo integrated.
- No changes to pre-existing examples or tests (beyond the verify.sh
  entry).
