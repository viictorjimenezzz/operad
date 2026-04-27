# Determinism in `operad.optim` / `operad.train`

For a training run to replay byte-for-byte against a recorded cassette,
every source of randomness must be pinned. This page lists every
user-facing seed surface in the training stack. Pin all of them, and a
`Trainer.fit()` run will produce the same `TrainingReport`,
`Agent.hash_content`, and `Optimizer.state_dict()` on every replay.

## Seedable surfaces

- **`DataLoader(shuffle=True, seed=...)`** — `operad/data/loader.py`.
  Default is `None` (OS-entropy shuffle). Pass an explicit `int` to pin
  batch order.
- **`random_split(dataset, ratios, seed=...)`** — pin the train/val
  partition; the split ordering feeds straight into the shuffled
  loader.
- **`EvoGradient(rng=random.Random(seed))`** — `operad/optim/optimizers/evo.py`.
  Mutation choice is drawn from this RNG. Default is a fresh
  unseeded `random.Random`; construct with an explicit seeded `rng`.
- **`Configuration.sampling.seed`** — `operad/core/config.py`. The seed
  passed to the backend's sampling call. Only matters while
  *recording*; on replay the response comes from the cassette so
  sampling is bypassed entirely.
- **Optimizers with intrinsic stochasticity** — `OPROOptimizer` and
  `APEOptimizer` sample proposals internally. They are replayable only
  when their underlying agents are deterministic (cassette replay)
  *and* any internal retries / candidate-count knobs are fixed.
  Prefer `TextualGradientDescent` or `MomentumTextGrad` when the goal
  is byte-for-byte reproducibility.

## Deterministic by construction (no user action required)

- `asyncio.gather` preserves *input* order across completions, so
  `backward()`, loss aggregation, and `Optimizer._apply_updates` produce
  results in a deterministic order regardless of which child finishes
  first.
- `Tape` entries are appended in call-start order, not completion
  order; UUID `event_id`s are cosmetic and are not consulted during
  backward propagation.
- `Optimizer.state_dict()` walks `named_parameters()` in declared
  traversal order, so the serialized dict keys are stable.
- `Agent.hash_content` hashes the JSON-serialized `state()`; Pydantic
  serialization is deterministic for the types used in `AgentState`.

## If replay drifts

`CassetteMiss` names the segment that diverged (`hash_model`,
`hash_prompt`, or `hash_input`). If replay drifts, compare the run's
seed surfaces against this list first; a missing seed is by far the
most common cause.
