# 5-4 — `PromptTraceback` — debugging the training loop

**Wave.** 5 (depends on 2-5, 3-1).
**Parallel with.** 5-1, 5-2, 5-3, 5-5.

## Context

When a training run produces a low-quality batch, the user needs to
walk the tape and see *what each agent saw*, *what it emitted*, and
*what critique flowed back*. `PromptTraceback` renders this in the
shape of a Python exception traceback, making debugging a
familiar-feeling activity.

Read `.context/NEXT_ITERATION.md` §13.11.

## Scope — in

### `operad/optim/traceback.py`

- `class PromptTraceback`:
  - Constructor: `tape: Tape, gradients: dict[str, TextualGradient]`
    (path → gradient, as produced by `backward()`).
  - Alternative constructor `PromptTraceback.from_run(tape, loss:
    TextualGradient)` that seeds gradients at the root and walks
    them via a lightweight re-propagation (reuse the dispatch rules
    in 3-1).
- Rendering:
  - `def __str__(self) -> str` — plain text, reverse-order walk of
    the tape, one stanza per node. Each stanza:

    ```
    File "agent://Pipeline.stage_2.reasoner", in forward
      Input:  {"text": "..."}
      Output: {"answer": "..."}
      Gradient: [severity=0.4] answer is correct but too long
    ```

    Mimicking Python traceback layout (hence the `File "..."`
    pseudo-URI).
  - `def __rich__(self)` — Rich-compatible rendering with colors,
    indentation per depth, and syntax-highlighted JSON payloads.
    Optional — only if `rich` is installed; fall back to `__str__`
    otherwise.
  - `def save(path)` — dump to an NDJSON file for later inspection.
  - `def to_markdown()` — render as a Markdown code-block list
    (useful for PR descriptions and incident reports).
- Entry point:
  - `def traceback(tape: Tape, loss: TextualGradient | None = None,
    gradients: dict | None = None) -> PromptTraceback`.
- Automatic integration (optional, opt-in):
  - A `TracebackOnFailure` callback (in `operad/train/callbacks.py`
    — coordinate with 5-3 author if 5-3 is touching that file
    concurrently; otherwise *here* add a new file
    `operad/train/callbacks_traceback.py` to avoid conflict):
    - Watches `on_batch_end`; if the batch's loss > user-specified
      threshold, construct a `PromptTraceback` and log/save it.

### Tests

- `tests/optim/test_traceback.py`:
  - Construct a tape via `tape()` + stubbed pipeline of 3 agents.
  - Build a `PromptTraceback(tape, gradients={...})`.
  - `str(tb)` contains stanzas for all 3 nodes in reverse order.
  - Stanza for the deepest leaf shows its input, output, gradient.
  - `to_markdown()` renders correctly.
  - `save("/tmp/tb.ndjson")` produces readable NDJSON.
  - `from_run(tape, loss)` uses the same propagation as `backward()`
    — verify by constructing both and comparing.

## Scope — out

- Do **not** modify 2-5's tape shape or 3-1's backward signature.
  The `PromptTraceback` is an *observer* of that data, never a
  producer.
- Do not introduce a UI beyond text / Rich / Markdown. No HTML
  renderer in this task (that's a later polish).
- Do not push the traceback into the jsonl observer automatically.
  The callback is opt-in.

## Dependencies

- 2-5: `Tape`, `TapeEntry`.
- 3-1: `backward()` propagation rules (imported for the alternative
  constructor).
- 1-1: `TextualGradient`.

## Design notes

- **Pseudo-URIs.** Use `agent://<dotted_path>` as the "File" URI.
  This makes editor integrations possible later (a custom protocol
  handler could jump to the agent definition).
- **Redaction.** Tapes may contain sensitive strings from user
  inputs. Provide a `redact: Callable[[BaseModel], BaseModel] |
  None = None` knob on `PromptTraceback` so production users can
  scrub values before rendering.
- **No heavy deps.** Rich is optional; `to_markdown` must work with
  only stdlib.
- **Formatting.** Wrap long JSON on dumps at 120 cols; truncate
  extremely long values (>2KB) with a "[truncated N chars]" marker.

## Success criteria

- `uv run pytest tests/optim/test_traceback.py` passes.
- `uv run ruff check operad/optim/traceback.py` clean.
- `from operad.optim import PromptTraceback, traceback` works.
- `PromptTraceback(tape, gradients=...)` renders all three nodes
  of a 3-stage pipeline in reverse order with distinguishable
  stanzas.
