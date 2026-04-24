# 1-5 — `UncertaintySampler` for active learning

**Wave.** 1. **Parallel with.** 1-{1..4,6}.

## Context

`operad.data` ships `SequentialSampler`, `RandomSampler`,
`WeightedRandomSampler`. Missing: a sampler that prioritizes
examples the current agent is *uncertain about*, so training
naturally focuses effort where the model is weakest. Classic active
learning, cheap to add.

## Scope — in

### `operad/data/active.py` (new file)

```python
class UncertaintySampler(Sampler):
    """Weight examples by a scorer's uncertainty (higher = sampled more).

    The scorer is typically a calibrated Critic agent whose `Score`
    output contains both a `score` and a `rationale`; uncertainty is
    derived as `1 - abs(score - 0.5) * 2` (peak at 0.5). Users can
    swap in their own uncertainty function.
    """

    def __init__(
        self,
        dataset: Dataset,
        agent: Agent,
        *,
        uncertainty_fn: Callable[[OperadOutput], float] | None = None,
        scorer: Agent | None = None,
        num_samples: int | None = None,
        seed: int | None = None,
        refresh_every: int = 1,
    ) -> None: ...

    def __iter__(self) -> Iterator[int]: ...
    def __len__(self) -> int: ...

    async def refresh(self) -> None:
        """Re-score the whole dataset through `agent` (+ `scorer`) and
        recompute per-example weights. Called at construction and
        every `refresh_every` epochs."""
```

Default `uncertainty_fn`:
- If `scorer` is provided: run scorer on each `(input, predicted)`
  pair; uncertainty = `1 - abs(scorer_score - 0.5) * 2`.
- If not: use self-consistency of the agent's own output across 3
  runs with different temperature; uncertainty = string-disagreement
  fraction. (Expensive; document the cost.)

### `operad/data/__init__.py`

Re-export `UncertaintySampler`.

### Tests

`tests/data/test_active.py`:

- Instantiate with a stubbed scorer whose `score` depends on
  example index (e.g., score=0.5 for even indices, 0.9 for odd).
  Confirm even indices get higher weight.
- `refresh_every=2` means weights only recompute every 2 epochs
  (mock `agent(x)` calls and count them).
- With `num_samples=3`, `__iter__` yields 3 indices; sampling is
  *with replacement* by default.
- `seed=7` → deterministic output.

## Scope — out

- Do not implement full active-learning loops (dataset augmentation,
  pool selection, oracle labeling). The sampler is the primitive;
  orchestration sits in `Trainer` or user code.
- Do not modify existing samplers.

## Dependencies

- `operad.data.loader.Sampler` protocol.
- `operad.core.agent.Agent`, `operad.core.output.OperadOutput`.
- `operad.benchmark.Dataset`.
- (Optional) `operad.agents.reasoning.components.critic.Critic` for
  the default scorer.

## Design notes

- **Refresh cost.** Refreshing on every epoch is expensive —
  scoring the whole dataset with an LLM. Default `refresh_every=1`
  but strongly recommend `>=2` for real runs. Document.
- **Uncertainty calibration.** If the scorer is uncalibrated,
  uncertainty is garbage. Add a one-liner in the docstring pointing
  at calibration literature; do not try to calibrate for the user.
- **Integration with Trainer.** Nothing special — user passes
  `DataLoader(train, sampler=UncertaintySampler(...))`. `Trainer`
  calls `sampler.refresh()` at the top of each epoch if the sampler
  has a `refresh` method (duck-typed).
- **Trainer integration is opt-in.** Make sure `Trainer` detects
  `hasattr(loader.sampler, "refresh")` and calls it under
  `no_grad()` to avoid tape pollution.

## Success criteria

- `tests/data/test_active.py` passes offline with a stubbed scorer.
- `uv run ruff check operad/data/active.py` clean.
- `from operad.data import UncertaintySampler` works.
- `Trainer.fit` with an `UncertaintySampler`-backed loader trains
  successfully on a 10-row synthetic dataset (no crash, no hang).
