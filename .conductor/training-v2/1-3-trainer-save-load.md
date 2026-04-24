# 1-3 — `Trainer.save` / `Trainer.load`

**Wave.** 1. **Parallel with.** 1-{1,2,4..6}. **Unblocks.** 2-5 (Studio).

## Context

Today callers can `freeze(agent, path, optimizer=opt)` to persist a
training checkpoint, then `thaw_pair(path)` to restore it. That's
the plumbing — but PyTorch-Lightning users reach for
`trainer.save()` / `Trainer.load()`. We add the convenience.

## Scope — in

### `operad/train/trainer.py`

Add two methods on `Trainer`:

```python
def save(self, path: str | Path) -> None:
    """Persist agent state + optimizer state + report history.

    Produces a single JSON file at `path` containing:
      - agent_state:   AgentState dump
      - optimizer_state: Optimizer.state_dict()
      - scheduler_state: LRScheduler.state_dict() or None
      - report: TrainingReport dump (per-epoch metrics, hashes)
      - metadata: {operad_version, python_version, saved_at_iso}
    API keys are scrubbed (matches freeze() existing behavior).
    """

@classmethod
def load(
    cls,
    path: str | Path,
    *,
    agent: Agent | None = None,       # optional structural shell
    loss_fn: Loss | None = None,
    optimizer_factory: Callable[[Agent], Optimizer] | None = None,
    scheduler_factory: Callable[[Optimizer], LRScheduler] | None = None,
    callbacks: list[Callback] | None = None,
) -> Trainer:
    """Restore a Trainer. When `agent` is None, thaw the Agent from the bundle."""
```

Semantics:
- `save` never mutates state, just writes a bundle.
- `load` is symmetric: without any kwargs it restores a fully usable
  `Trainer` from scratch; with an `agent` kwarg it *overlays* saved
  state onto the caller's structural shell (useful when the user
  wants to keep their own composite class intact).

### `operad/core/freeze.py`

No changes — reuse `freeze()` / `thaw_pair()` as the storage layer.
`Trainer.save/load` just compose them with extra bundle keys.

### Tests

`tests/train/test_save_load.py`:

- Round-trip a `Trainer(agent, TextualGradientDescent(...), loss_fn)`:
  `t.save("/tmp/t.json")` → `Trainer.load("/tmp/t.json")` gives back
  a trainer whose `optimizer.state_dict` matches and whose agent
  `hash_content` matches.
- A partial fit (1 epoch) → save → load → continue fit (1 more
  epoch). Total improvement ≥ improvement over 2 fresh epochs
  (non-strict: confirm training continues, not that it's better).
- `save()` redacts API keys from any nested `Configuration`.

## Scope — out

- Do not add a versioned checkpoint directory (e.g., `checkpoints/epoch_3.json`).
  Single-file round trip only. Callers can build directory
  structures with `BestCheckpoint` + ordinary filesystem naming.
- Do not serialize `Dataset` / `DataLoader`. Callers re-create
  those before `load`.
- Do not change `freeze()` semantics.

## Dependencies

- `operad.core.freeze.freeze`, `thaw_pair` (existing from §5-3).
- `operad.optim.Optimizer.state_dict / load_state_dict`.

## Design notes

- **Callable factories for load.** Optimizers and schedulers hold
  references to arbitrary rewriter agents; serializing/reviving those
  verbatim is tricky. The cleanest API is for the caller to pass
  factories (`optimizer_factory(agent) -> Optimizer`) and the
  `load` method `load_state_dict(...)` into them. Document this as
  the primary API; a convenience `Trainer.quick_load` for default
  `TextualGradientDescent` setups can come later.
- **Bundle format.** JSON (not pickle). Keeps files diffable, matches
  `freeze()`.
- **metadata.saved_at_iso**: UTC ISO 8601 — not a runtime check; just
  for humans.
- **No side effects on disk beyond `path`.** Don't write logs, temp
  files, or caches during save.

## Success criteria

- `uv run pytest tests/train/test_save_load.py -v` passes.
- `uv run ruff check operad/train/trainer.py` clean.
- Bundle is valid JSON when read with `json.load()`.
- Existing `BestCheckpoint` tests still pass (no `freeze()` churn).
