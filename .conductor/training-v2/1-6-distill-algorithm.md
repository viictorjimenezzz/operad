# 1-6 — `Distill(teacher, student)` algorithm

**Wave.** 1. **Parallel with.** 1-{1..5}.

## Context

Distillation is a cheap, high-value composition: run a big/expensive
teacher agent on a dataset to collect `(input, teacher_output)`
trajectories; train a small student agent to match those outputs.
All primitives exist — this is composition, not invention.

## Scope — in

### `operad/algorithms/distill.py` (new file)

```python
class Distill(Generic[In, Out]):
    """Train a student agent to mimic a teacher on a dataset.

    Runs in two phases:
      1. Collect — teacher(x) on every dataset row; store pairs.
      2. Train — Trainer.fit(student, loss=StudentMatchLoss(teacher outputs), dataset=...)
    """

    def __init__(
        self,
        teacher: Agent[In, Out],
        student: Agent[In, Out],
        *,
        optimizer_kind: Literal["textgrad", "momentum", "evo"] = "textgrad",
        lr: float = 1.0,
        epochs: int = 3,
        match_fn: Callable[[Out, Out], tuple[float, TextualGradient]] | None = None,
        metrics: list[Metric] | None = None,
    ) -> None: ...

    async def run(
        self,
        dataset: Iterable[In] | Dataset,
    ) -> Agent[In, Out]:
        """Collect teacher outputs, train student, return trained student."""
```

### `operad/algorithms/losses.py` (new, or `operad/optim/loss.py`
extension — pick whichever file-partitioning makes sense)

```python
class StudentMatchLoss(Loss):
    """Reward the student for matching the teacher's output.

    `match_fn` default:
      - if Out has only string fields → Rouge1
      - if Out is a numeric/bool → exact match
      - else → JSON field-equality with per-field gradient messages.
    """
```

### `operad/algorithms/__init__.py`

Re-export `Distill`.

### Tests

`tests/algorithms/test_distill.py`:

- FakeTeacher deterministically returns `Out` for each `In`.
- Student starts with a weak prompt; `Distill.run(dataset)` returns
  a student with improved `StudentMatchLoss` score on the dataset
  (offline, with stubbed rewriters).
- Teacher and student use different `Configuration`s (`backend`,
  `model`, `sampling`) — no mixup.
- `epochs=0` short-circuits: returns the seed student unmodified.

## Scope — out

- Do not implement knowledge-distillation tricks (soft targets, KL
  divergence). Prompt-level distillation is the target here; the
  name stays `Distill` but the scope is "make the student produce
  teacher-quality outputs."
- Do not fuse teacher + student into a single model. They stay as
  separate Agents; teacher is frozen throughout (`mark_trainable()`
  NOT called on it).

## Dependencies

- `operad.train.Trainer` (existing).
- `operad.optim.*` optimizers (existing).
- `operad.metrics.rouge.Rouge1` (existing) for default `match_fn`.

## Design notes

- **Teacher freezing.** During collect, never call `backward()` on
  the teacher — wrap teacher calls in `no_grad()` to skip tape.
- **Dataset shape.** Accept either `Dataset[In, Out]` (existing
  operad shape) or a bare `Iterable[In]`. In the second case,
  `expected` for each row is the teacher's output for that input.
- **Caching.** Teacher outputs are expensive; cache them in memory
  during the run. Disk caching is not in scope (users can use
  existing cassette replay for that).
- **Match_fn design.** Returns `(float_score, TextualGradient)` so
  it can drop directly into any `Trainer` without adaptation.
  Default should handle 80% of cases; power users override.
- **Optimizer choice.** Default `"textgrad"` fits the prompt-
  distillation story. `"evo"` is fine when the student has many
  prompt-level knobs; document as trade-off.

## Success criteria

- `tests/algorithms/test_distill.py` passes offline.
- `uv run ruff check operad/algorithms/distill.py` clean.
- `from operad.algorithms import Distill` works.
- Student's `hash_content` after `Distill.run` ≠ seed's; default
  metrics improve.
