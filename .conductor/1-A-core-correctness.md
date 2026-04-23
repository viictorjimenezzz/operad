# Phase 1 · Stream A — Core correctness

**Goal.** Close the build-time footguns named in `ISSUES.md` §A and
fix the init-order issue. Every other stream builds on top of the error
taxonomy and `Configuration` shape you leave behind, so ship carefully.

**Owner:** one agent.
**Blocks.** Phase-2 streams C, D, E — they extend what you settle.
**Addresses:** A-1, A-2, A-3, A-4, A-5, A-6, A-7, B-3, B-4, D-4.

---

## Scope

### Files you will edit
- `operad/core/build.py` — sentinel proxy, init-order reorder,
  shared-child detection.
- `operad/core/config.py` — add `timeout`, `max_retries`,
  `backoff_base`; decide on `reasoning_tokens`.
- `operad/utils/errors.py` — new `BuildReason` literals (`payload_branch`
  at minimum).
- `operad/models/bedrock.py` — stop silently dropping `top_k` / `seed`.
- `operad/models/openai.py` — thread `reasoning_tokens` if you keep the
  field.
- `operad/models/__init__.py` — docstring table summarising per-backend
  `extra` handling.
- `operad/models/lmstudio.py` — document the `"lm-studio"` fallback in
  the module docstring.
- `operad/metrics/deterministic.py` — fix `Latency.score()`.
- `operad/agents/reasoning/react.py:89` — type `config: Configuration`.
- `tests/test_build.py`, `tests/test_configuration.py`,
  `tests/test_metrics_deterministic.py` — new coverage.

### Files to leave alone
- Anything under `operad/agents/{coding,conversational,memory}/` (other
  streams).
- `operad/runtime/observers/` (Stream C).
- `operad/algorithms/` except importing a new `BuildReason` if needed.

---

## Design direction

### A-1 · Sentinel proxy

The tracer builds `child.input.model_construct()` as a sentinel and
returns `child.output.model_construct()` as the fake result. This
works for structural routing but silently tolerates `if x.flag: ...`
inside a composite `forward`.

Build a sentinel mechanism that:

1. **Preserves `isinstance`.** `Tracer.record` and `Agent.invoke` both
   do `isinstance(x, child.input)`; a plain `__getattr__` wrapper fails
   these. Subclass the input model via `type(name, (cls,), dict(...))`
   or a metaclass that intercepts attribute reads.
2. **Raises `BuildError("payload_branch", ...)`** when a composite's
   `forward` reads any field of a sentinel input during tracing.
3. **Does not intercept dunder or pydantic-internal access** — the
   class still needs to behave like a valid Pydantic instance for
   validators that run during `model_construct`.
4. **Is installed by `_trace` for the root sentinel** and by
   `Tracer.record` whenever it recursively calls a composite child's
   forward (line 131–143 today).

Leaves receive normal `model_construct()` instances: the default
`forward` does not read fields during trace — it just formats them
into a string for strands.

### A-3 · Pass reorder

Reorder `abuild_agent` to:

1. `for a in _tree(root): _validate(a)`
2. `tracer = Tracer(root); out = await _trace(root, tracer)`
3. On success, `for a in _tree(root): _init_strands(a)`

**Caveat.** If the root is a *leaf* (no overridden `forward`), then
`_trace` calls `root.forward(sentinel)` which calls
`strands.Agent.invoke_async` — and that requires strands to be
initialised. Options:

- Init strands only on the root before trace, rest after. Minimally
  invasive.
- Skip `_trace` entirely for leaf roots (nothing to trace anyway) and
  just validate + init.

Pick whichever is simpler once you have tests in place. The goal is
*no orphaned strands state on tracing failure for composite roots*.

### A-2 · Shared-child warning

In `abuild_agent` (or a helper), count `id(a)` occurrences while
walking. If any agent appears under more than one parent, emit
`warnings.warn(...)` with both parent paths. Not a `BuildError` — sharing
is occasionally useful — but surface it so footguns are visible.

### A-4, A-5 · Backend knob plumbing

- `reasoning_tokens`: the cleanest move is to keep the field and
  thread it through OpenAI's `reasoning_effort` / `max_completion_tokens`
  where applicable. Document per-backend support at the top of
  `operad/models/__init__.py`. If that turns out to require too much
  per-backend sniffing, delete the field and push users to `extra`.
- Bedrock `top_k`/`seed`: strands' `BedrockModel` accepts
  `additional_request_fields`. Thread both there if non-None. If strands
  does not, raise a clear `BuildError("trace_failed", ...)` at
  `_init_strands` time.

### A-6 · `extra` dict semantics doc

Add a short table in the `operad/models/__init__.py` module docstring:

```
| Backend   | `extra` destination             |
| --------- | ------------------------------- |
| llamacpp  | splatted as kwargs              |
| ollama    | wrapped as `options` dict       |
| openai    | forwarded via `extra_body`      |
| lmstudio  | (inherits openai behaviour)     |
| bedrock   | splatted as `additional_request_fields` |
```

If you can cheaply make `openai` honour `extra_body`, do it here.

### A-7 · `Latency.score`

```python
async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
    if not self._measurements:
        return 0.0
    return 1.0 / (1.0 + self._measurements[-1])
```

Docstring explains the `measure() → score()` pairing. Keep `measure()`
unchanged.

### B-3 · Configuration knobs

Add plain fields:

```python
timeout: float | None = None        # seconds
max_retries: int = 0
backoff_base: float = 0.5           # seconds, exponential
```

Thread into each backend adapter where the underlying SDK exposes a
matching knob. **Do NOT implement retry logic here** — just wire the
fields so later streams can consume them. Observer-driven retries live
in Stream C's follow-up.

### D-4 · `ReAct.__init__` config typing

```python
def __init__(self, *, config: Configuration) -> None:
    super().__init__(config=None, input=Task, output=Answer)
    ...
```

Drop the `# type: ignore[no-untyped-def]`.

---

## Tests you must ship

- `tests/test_build.py::test_payload_branch_raises` — a composite that
  reads `x.some_field` inside `forward` fails `build()` with
  `BuildError.reason == "payload_branch"`.
- `tests/test_build.py::test_init_order` — if tracing fails,
  `strands.Agent.__init__` was NOT called on any leaf (spy on a
  `FakeLeaf` that subclasses a tracker).
- `tests/test_build.py::test_shared_child_warning` — assigning the same
  child to two attributes emits exactly one warning.
- `tests/test_configuration.py::test_new_fields` — timeout / retries /
  backoff_base round-trip.
- `tests/test_metrics_deterministic.py::test_latency_score_is_useful`.

---

## Acceptance

- `uv run pytest tests/` passes.
- A composite that branches on payload fails `build()` with a clear
  message pointing at the offending field read.
- No new imports from `strands` outside `operad/models/` and
  `operad/core/build.py`.

---

## Watch-outs

- `isinstance` checks in `Tracer.record` must still succeed with the
  sentinel proxy — test this first with a throwaway script before
  wiring it into the tracer.
- Don't "improve" unrelated error messages while you're in
  `utils/errors.py`.
- Leaf-rooted `build()` is a subtle edge case; see the A-3 Caveat above.
- `Configuration` uses `extra="forbid"` — remember to update
  `test_configuration.py` if you add fields.
