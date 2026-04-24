# 2-3 — Rewrite agents library

**Wave.** 2 (depends only on `Agent` + existing render stack).
**Parallel with.** 2-1, 2-2, 2-4, 2-5.
**Unblocks.** 3-2 (`Optimizer.step()`).

## Context

An `Optimizer` consumes `(Parameter, TextualGradient)` pairs and
applies the gradient to produce a new parameter value. The "apply"
step is an LLM call: given the old value and the critique, produce a
new value that addresses the critique while respecting the
parameter's constraint.

Each parameter kind (role, task, rules, examples, temperature,
categorical) needs its own specialized rewrite prompt. These are
first-class `Agent` subclasses (so they get cassette caching, hashes,
observer events for free).

Read `operad/agents/reasoning/components/` (any leaf, e.g.
`reflector.py`) for the pattern, then `.context/NEXT_ITERATION.md` §7.1.

## Scope — in

### `operad/optim/rewrite.py`

- Input/output schemas (Pydantic):
  - `RewriteRequest(BaseModel)`:
    - `old_value: str` (string-serialized current value)
    - `gradient: str` (the critique `message`)
    - `gradient_by_field: dict[str, str] = {}`
    - `severity: float`
    - `lr: float` (scales how aggressive the rewrite should be)
    - `constraint_hint: str` (plain-English description of the
      parameter's constraint — e.g., "string, ≤ 500 chars, no
      forbidden substrings X, Y")
    - `parameter_kind: str` (`ParameterKind` value, for prompt
      disambiguation)
  - `RewriteResponse(BaseModel)`:
    - `new_value: str`
    - `rationale: str = ""`
- Base class:
  - `class RewriteAgent(Agent[RewriteRequest, RewriteResponse])` with
    sensible defaults (`role`, `task`, `rules`, `examples`) for
    "rewrite this value to address the gradient without violating
    the constraint."
- Kind-specialized subclasses with opinionated prompts:
  - `TextRewriter` — role/task rewriter (string).
  - `RuleListRewriter` — `old_value` is a JSON-encoded list; response
    parses back.
  - `ExampleListRewriter` — same idea for `Example[In, Out]` lists;
    the `constraint_hint` includes the Pydantic `In` / `Out` schemas
    so the LLM emits valid typed examples.
  - `FloatRewriter` — numeric parameters; output must be a stringified
    number. Strict sampling (`temperature=0.0`, `max_tokens=32`).
  - `CategoricalRewriter` — pick a value from a vocabulary; response
    must be one of the allowed tokens. Deterministic sampling.
- A registry mapping `ParameterKind` → `RewriteAgent` class:
  - `REWRITE_AGENTS: dict[ParameterKind, type[RewriteAgent]]`.
  - `def rewriter_for(kind: ParameterKind) -> type[RewriteAgent]`.
- Helper `def apply_rewrite(param: Parameter, grad: TextualGradient,
  rewriter: RewriteAgent, *, lr: float) -> Awaitable[None]` that:
  1. Constructs a `RewriteRequest` from the current param value + grad + lr.
  2. Invokes the rewriter.
  3. Parses `new_value` into the right type (`TextParameter` → string
     pass-through; `RuleListRewriter` → parse JSON; `FloatRewriter`
     → `float(new_value)`; etc.).
  4. Validates against `param.constraint`; on violation, *retry once*
     with a tightened prompt, then raise a clear error.
  5. Writes the validated value back via `param.write(...)`.

### `operad/optim/__init__.py`

Export `RewriteAgent`, the five kind-specific subclasses,
`REWRITE_AGENTS`, `rewriter_for`, `apply_rewrite`, and the
`RewriteRequest` / `RewriteResponse` schemas.

### `tests/optim/test_rewrite.py`

- Each `RewriteAgent` subclass constructs cleanly with `config=None`
  and `build()` is deferred until actually used.
- **Offline test with a stubbed rewriter**: subclass `TextRewriter`,
  override `forward` to deterministically return
  `RewriteResponse(new_value=request.old_value + " [revised]")`.
  Run `apply_rewrite(param, grad, rewriter, lr=1.0)` and assert the
  param's underlying agent attribute now ends with `" [revised]"`.
- Constraint violation path: `TextParameter(constraint=TextConstraint(max_len=5))`
  with a stub returning a 20-char string should raise with a
  descriptive error after the retry.
- `FloatRewriter` correctly parses numeric string output.
- `CategoricalRewriter` rejects out-of-vocab responses.
- `REWRITE_AGENTS` has entries for every `ParameterKind`.

## Scope — out

- Do **not** implement `Optimizer` or `.step()` — that is 3-2.
- Do not wire `apply_rewrite` into a training loop — that is 4-3.
- Do not write the gradient-producing side (`Backprop` agents) —
  that is 2-4.
- Do not hook into the `tape` — this module does not know about it.

## Dependencies

- `operad.core.agent.Agent`.
- Wave 1-1: `Parameter`, `TextualGradient`, `ParameterConstraint`,
  `ParameterKind`.
- `operad.core.render` (via default `Agent` renderer) — no new work.

## Design notes

- **Prompts matter.** Each rewriter's `role` / `task` / `rules`
  should be carefully hand-crafted for its kind. Take inspiration
  from TextGrad's open-source prompts and DSPy's `Prompt Evolution`
  prompts. These are *the* differentiator between a working and a
  flailing optimizer.
- **LR as prompt knob.** `lr >= 0.9` → "Rewrite from scratch using
  the gradient as the primary guide." `lr <= 0.2` → "Make the
  smallest possible edit that addresses the gradient." `lr in (0.2,
  0.9)` → graded phrasing. The mapping is a rewriter-internal
  concern; document it in the rewriter's docstring.
- **No global state.** Each `RewriteAgent` subclass is pure — no
  shared cache, no module-level LLM. The instance's `config`
  controls the backend.
- **Serializability.** `RewriteRequest` / `RewriteResponse` round-trip
  via `model_dump_json()` so cassette replay just works.
- **Default sampling.** `FloatRewriter` / `CategoricalRewriter`
  should ship `default_sampling = {"temperature": 0.0, "max_tokens": 64}`
  class-level. Text rewriters ship `{"temperature": 0.7}`.

## Success criteria

- `uv run pytest tests/optim/test_rewrite.py` passes with stubbed
  rewriters (no real LLM calls).
- `uv run ruff check operad/optim/rewrite.py` is clean.
- `from operad.optim import RewriteAgent, TextRewriter, ...` works.
- `apply_rewrite(...)` mutates the underlying agent attribute through
  `Parameter.write()`.
- No edits outside `operad/optim/` and `tests/optim/`.
