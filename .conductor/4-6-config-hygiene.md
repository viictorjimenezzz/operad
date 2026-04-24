# 4 · 6 — Config hygiene: dead knobs, entry validation, switch side-effects

**Addresses.** M-2 (dead sampling knobs silently ignored), M-4 (Entry
construction has no runtime schema validation), M-6 (Switch tracer
invokes every branch with side effects). Bundled because each is
small, they share no surface, and splitting into three PRs would churn
reviewers. See [`../ISSUES.md`](../ISSUES.md) Group F.

**Depends on.** Nothing in Wave 4.

**Blocks.** Nothing critical — these are polish. The demos (6-1)
benefit from all three.

---

## Required reading

- `operad/core/config.py` — `Configuration`, `Sampling`, `Resilience`,
  `IOConfig`, `Runtime`. Note `Sampling.reasoning_tokens`.
- `operad/core/models/` — each backend adapter (anthropic, openai,
  bedrock, llamacpp, ollama, lmstudio, huggingface, gemini). Learn
  which ones actually use `reasoning_tokens`.
- `operad/benchmark/entry.py` + `operad/benchmark/dataset.py` —
  `Entry.__init__` and `Dataset.__init__`.
- `operad/agents/reasoning/switch.py` — the `Switch` composite and
  its tracer-specific fast path.
- `tests/core/test_config.py`, `tests/benchmark/test_benchmark.py`,
  `tests/agents/test_switch.py`.

---

## Goal

Close three silent-failure gaps by adding focused warnings /
validations where users currently get no signal.

## Scope

### M-2 · Warn on dead sampling knobs

Audit `Sampling` fields against each backend's adapter.
`reasoning_tokens`, `top_k` (some backends), seed (some backends), and
possibly `max_tokens` edge cases are candidates.

For each such field:

- Record, in a module-level dict in `operad/core/models/__init__.py`
  (or a new `_capabilities.py`), which backends honour which field.
- In `resolve_model(cfg)` (called from `_init_strands`), after model
  construction, iterate `cfg.sampling.model_fields_set` — fields the
  user explicitly set — and emit one `warnings.warn(...)` per field
  that the target backend does not honour.

Warning text:

```
UserWarning: Configuration.sampling.reasoning_tokens is set but
backend 'llamacpp' does not consume it; the value will be ignored.
```

Do not raise. The field is honest-silent-ignored today; warning makes
it loud.

### M-4 · Runtime schema validation for `Entry`

Today `Dataset([(a, b), ...])` coerces raw tuples to `Entry(input=a,
expected_output=b)` without verifying that `a` / `b` match the
dataset's claimed `In` / `Out` types. Errors surface later at metric
time with unhelpful messages.

- Add `Dataset.__init__(rows, *, in_cls=None, out_cls=None, ...)` —
  optional kwargs that, when set, run `in_cls.model_validate(...)` on
  every `Entry.input` and `out_cls.model_validate(...)` on every
  `Entry.expected_output` that isn't None.
- When both kwargs are omitted, the dataset infers from the first
  row (current behaviour) — but in that case, still run
  `.model_dump(mode="json")` on each input/expected to confirm
  Pydantic round-trip works; raise `ValueError` on the first bad row
  with `index=N, reason="..."`.
- The inference path already exists in `Dataset.load(...)`; reuse it.

### M-6 · `Switch` tracer branch-side-effect audit

`Switch.forward` at trace time invokes every branch with a sentinel.
If a branch's own `forward` calls a real API — e.g. a `ToolUser` that
queries the internet — the trace runs the API call silently.

Three-step fix:

1. Document the behaviour in `Switch`'s class docstring: "During
   build, every branch is invoked with a sentinel input to record
   edges. Branches must remain side-effect-free during symbolic
   trace; if a branch needs to call a real API, do it inside a leaf
   child of the branch, not in the branch's `forward` itself."
2. Add a deprecation warning at the top of `Switch.forward`'s
   tracer fast path: when `_TRACER.get() is not None`, emit
   `warnings.warn("Switch is tracing all branches; ensure they are
   side-effect-free. See Switch docstring.", SideEffectDuringTrace,
   stacklevel=3)` — where `SideEffectDuringTrace` is a new
   `UserWarning` subclass in `operad/utils/errors.py`. Users can
   silence per-composite via `warnings.filterwarnings`.
3. Unit test: attach a stub observer to detect the warning; assert
   it fires exactly once per `Switch.build()`.

---

## Verification

- M-2:
  - Unit test per-backend: set `cfg.sampling.reasoning_tokens=1`, call
    `resolve_model`, assert exactly one warning fires with the
    backend's name and the field name in the text.
  - Backends that *do* honour the field (e.g. `anthropic` with o1-class
    models) must not warn.
- M-4:
  - Unit test: `Dataset([(A(text="x"), A(text="y"))], in_cls=A,
    out_cls=A)` validates cleanly.
  - Unit test: `Dataset([("bad", "row")], in_cls=A, out_cls=A)` raises
    `ValueError` with index=0.
  - Backwards compat: `Dataset([...])` with no `in_cls`/`out_cls`
    behaves as before for valid rows.
- M-6:
  - Unit test: build a `Switch` with two trivial branches, capture
    warnings via `pytest.warns`, assert `SideEffectDuringTrace` fires
    once.
  - Existing `tests/agents/test_switch.py` tests still pass
    (`pytest.warns` doesn't affect them).
- `scripts/verify.sh` green.

---

## Out of scope

- Rewriting `Switch`'s tracer to invoke only one branch (would lose
  the full type-check coverage). The warning is the right
  deliverable.
- Making `Sampling` raise on dead knobs (would break existing users
  who set `reasoning_tokens` hopefully). Warn, don't raise.
- Pydantic Mode switching for `Entry` (strict vs coerce). Whatever the
  Pydantic default is, keep it; we just need the error to happen at
  construction, not at metric time.

---

## Design notes

- The capability table in `operad/core/models/` should be tiny
  (~20-line dict). Don't overengineer it into a schema.
- For M-2, a single `warnings.warn` per field per `resolve_model`
  call is enough; callers constructing 1000 leaves will see 1000
  warnings. If that's annoying, add a `warnings.simplefilter("once",
  ...)` wrapper — but the default is fine.
- `SideEffectDuringTrace` as a dedicated warning class lets users
  silence it globally with a one-liner.
