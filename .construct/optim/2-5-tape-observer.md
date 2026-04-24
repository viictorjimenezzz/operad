# 2-5 — Tape + TapeObserver

**Wave.** 2 (depends only on existing runtime observer stack).
**Parallel with.** 2-1, 2-2, 2-3, 2-4.
**Unblocks.** 3-1 (`backward()`).

## Context

The forward pass of a training step must record enough information
about every leaf invocation that `backward()` can walk the graph in
reverse and reason about each node. In the current observer model,
every `invoke` already emits `start` / `end` / `error` / `chunk`
events with `run_id`, `agent_path`, `input`, `output`, and metadata.
We simply accumulate those into an ordered `Tape`.

Read `operad/runtime/observers/base.py`, the existing
`operad/runtime/trace.py`, and `.context/NEXT_ITERATION.md` §4.

## Scope — in

### `operad/optim/tape.py`

- Data types (Pydantic or dataclass):
  - `class TapeEntry`:
    - `run_id: str`
    - `agent_path: str` — dotted path within the run's tree
    - `agent_ref: weakref.ref[Agent]` — for parameter lookup at
      backward time (live references, not copies)
    - `input: BaseModel`
    - `output: BaseModel`
    - `rendered_prompt: str | list[dict] | None` — best-effort capture
    - `started_at: float`
    - `finished_at: float`
    - `event_id: str` — stable key for correlation with the jsonl observer
    - `is_leaf: bool`
    - `metadata: dict[str, Any] = {}`
  - `class Tape`:
    - `entries: list[TapeEntry]` in invocation-start order
    - `root_input: BaseModel | None`
    - `root_output: BaseModel | None`
    - Methods:
      - `entries_in_reverse() -> Iterator[TapeEntry]` — for `backward()`
      - `entry_for_path(path: str) -> TapeEntry | None`
      - `children_of(path: str) -> list[TapeEntry]`
      - `parents_of(path: str) -> list[TapeEntry]`
      - `to_jsonl(path: Path)` — dump for debugging
- `class TapeObserver(Observer)`:
  - `__init__(self, tape: Tape, *, capture_prompts: bool = True)`
  - `async def on_event(self, event)`:
    - On `start`: record nothing (we need output too).
    - On `end`: construct `TapeEntry`, fetch the agent via
      `_PATH_STACK` if possible, capture rendered prompt (via a
      helper on the target agent — see design notes), append.
    - On `error` / `chunk`: skip.
  - Guard against double-registration; idempotent `register` /
    `unregister`.
- Context manager `operad.optim.tape`:
  - `@contextlib.asynccontextmanager async def tape() -> AsyncIterator[Tape]`
    that yields a fresh `Tape`, registers a `TapeObserver` on the
    global `registry`, ensures `_GRAD_ENABLED` (from 2-1) is respected
    (do not record if False), and un-registers on exit.
  - Nested `tape()` calls should raise a clear `RuntimeError` —
    we do not support nesting, and hiding it silently would make
    backward tapes subtly wrong.
- Utility: `def enabled() -> bool` that checks `_GRAD_ENABLED` (so
  downstream code can branch on whether a tape is active).

### `operad/optim/__init__.py`

Export `Tape`, `TapeEntry`, `TapeObserver`, `tape`.

### `tests/optim/test_tape.py`

- Running `agent(x)` inside `tape()` populates a non-empty `Tape`.
- Leaf-only agent: one entry whose `agent_path` is `type(agent).__name__`.
- `Pipeline(A, B)`: three entries — outer `Pipeline`, inner `A`, inner `B`
  — in forward order. `entries_in_reverse()` yields them in reverse.
- `Parallel({"a": A, "b": B})`: four entries (outer + 3 children) in
  forward-start order. `children_of("Parallel")` returns both child
  entries.
- A run that raises mid-pipeline still leaves a partial tape (entries
  up to the failure point); the context manager re-raises the error.
- Nested `tape()` raises `RuntimeError`.
- Inside `no_grad()` (from 2-1), `tape()` still works, but no
  `TapeEntry`s are recorded — the tape stays empty. (Document: you
  probably don't want to nest these, but we define the semantics.)
- `to_jsonl()` dumps readable NDJSON.
- **Reference integrity**: `TapeEntry.agent_ref()` returns the live
  agent instance; after the agent is dropped, the weakref returns
  `None` (do not crash the tape).

## Scope — out

- Do **not** implement `tape.backward(loss)` — that is 3-1 (but you
  may stub it as `raise NotImplementedError` if the naming is
  required for imports; prefer leaving it out).
- Do not wire tape recording into training — that is 4-3.
- Do not modify the existing `operad/runtime/trace.py` or
  `operad/runtime/observers/*` modules. You *use* them; you don't
  change them.

## Dependencies

- `operad.runtime.observers.base.{Observer, AgentEvent, registry,
  _RUN_ID, _PATH_STACK}`.
- `operad.core.agent.Agent` (for type hints, weakrefs).
- `operad.optim.context._GRAD_ENABLED` (from 2-1; if 2-1 hasn't
  merged yet, guard with `try: from operad.optim.context import
  _GRAD_ENABLED; except ImportError: _GRAD_ENABLED = None` — the
  fallback always records; document this).

## Design notes

- **Capturing rendered prompts.** At `end`-event time, the agent's
  declared state is unchanged, so we can re-render via the agent's
  built-in renderer (call something like
  `agent.format_system_message()` — check the exact method name in
  `operad/core/agent.py`). Make this opt-out via
  `capture_prompts=False` for expensive renders.
- **Path resolution.** Use `_PATH_STACK.get()` to fetch the current
  path. If that's `None` (observer fired outside an invoke), skip
  the entry.
- **Run isolation.** `Tape` belongs to one root-run only. If a user
  accidentally opens two `tape()` contexts (even sequentially) in
  the same process, the second gets a fresh `Tape`. No globals.
- **Memory bound.** Each entry is small (O(KB)). For a 1000-step
  batch, we're at O(MB). Don't try to be clever with compression;
  just document the cost.
- **Future: `tape.backward(loss)` will live in 3-1.** You may add a
  `backward` method on `Tape` in 2-5 that raises
  `NotImplementedError("implemented in operad.optim.backward")`, so
  the import surface is stable; but it's cleaner to leave that for
  3-1 and add a free function `backward(tape, loss)` that rebinds
  onto `Tape` via monkeypatching. Choose whichever you prefer; flag
  in the PR.

## Success criteria

- `uv run pytest tests/optim/test_tape.py` passes offline with
  `FakeLeaf`-style agents.
- `uv run ruff check operad/optim/tape.py` is clean.
- `from operad.optim import Tape, TapeObserver, tape` works.
- `async with tape() as t: await agent(x)` yields a populated `Tape`.
- No edits to `operad/runtime/` or existing observer modules.
