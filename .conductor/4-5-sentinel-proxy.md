# 4 · 5 — Sentinel proxy for composite payload-branching

**Addresses.** H-6 — VISION §7 iteration-4 commitment. Composite
`forward()` can silently branch on payload values during symbolic
tracing today; Pydantic field defaults make the "wrong" branch look
fine. See [`../ISSUES.md`](../ISSUES.md) Group E.

**Depends on.** Nothing in Wave 4.

**Blocks.** Nothing strictly. Sentinel is independent — 5-1
(auto_tune) and 5-2 (dashboard) don't require it, but the showcase
demo (6-1) will depend on it for correctness.

**Time-box.** **One week.** If the proxy proves as subtle as
`torch.fx`, ship an AST-scan *warning* fallback (see "Fallback" below)
instead of a hard error.

---

## Required reading

- `VISION.md` §5.3 (the build step) and §7 ("sentinel proxy: detect
  payload-branching in composites at trace time").
- `operad/core/build.py` — especially `_make_sentinel`,
  `_PayloadBranchAccess`, and how `Tracer.record` handles the child
  `forward` sentinel call. The build already has a basic sentinel
  that raises on declared-field reads; we're extending it to catch
  branching on field *values* (e.g. comparing them, truthy checks,
  iterating them).
- `operad/utils/errors.py` — `BuildError`, `BuildReason`.
- `operad/agents/pipeline.py`, `operad/agents/parallel.py`, and
  `operad/agents/reasoning/react.py` — reference composites the
  sentinel must not false-positive on.
- `tests/core/test_build.py` and `tests/core/test_errors.py`.

---

## Goal

Make composite `forward()` methods that branch on payload values fail
at `build()` time with a pointed `BuildError("payload_branch", ...)`
that names the offending field and the call site.

## Scope

### Extend `_make_sentinel`

Today the sentinel raises `_PayloadBranchAccess` on any declared-field
read. That catches `x.field` but not:

- `if x:` (dunder `__bool__`)
- `x == y` (dunder `__eq__`)
- `x != None` (dunder `__ne__`)
- `if "foo" in x.field_list:` — handled by field read already
- comparisons on the payload as a whole (`if x > y:`)

Extend the dynamically-built subclass to raise on:

- `__bool__`
- `__eq__`, `__ne__`, `__lt__`, `__le__`, `__gt__`, `__ge__`
- `__hash__` — Pydantic models aren't hashable by default but compound
  models can be; raise to be safe
- `__iter__`, `__len__`, `__contains__`

Each raise should carry the dunder name so the error message is
specific (`"composite compared a sentinel via __eq__"`).

### Richer error

Upgrade `BuildError("payload_branch", ...)` to include:

- `cls_name` and `field_name` (or dunder name) — already present.
- A **file + line** pointer to the offending `if`/`for`/comparison.
  Capture with `traceback.extract_stack()` at the point of the dunder
  raise. Walk up the stack to the first frame whose filename is not
  in `operad/core/` — that's the user's composite `forward`.
- A Mermaid fragment (existing pattern) showing the composite node.

Error text example:

```
BuildError(payload_branch): Pipeline.stage_1.forward read
    Question.text via __bool__ at pipeline.py:42 during trace.
    Route on a child's typed output (e.g. Switch over a Literal choice)
    instead of the payload value.
```

### Apply to root trace too

`_trace(root, tracer)` in `build.py` already wraps the root forward
with sentinel semantics for composites. Extend the same wrapping to
catch dunder traps (not just `_PayloadBranchAccess` on fields).

### Fallback (if time-boxed)

If the proxy proves too fragile (e.g. false-positives on legitimate
`isinstance(sentinel, SomeType)`), replace the hard error with:

- An `ast.parse(inspect.getsource(forward))` scan over the composite's
  `forward` method.
- Walk the AST. Any `If`/`While`/`For`/`Compare` node whose test
  reads from the `forward` parameter → emit a `warnings.warn(...)`.
- No `BuildError`, just a heads-up.

Document the fallback path in the brief's PR description and update
VISION §5.3 to describe the current state.

---

## Verification

- Unit test: a composite that does `if x.text:` in `forward` → raises
  `BuildError("payload_branch", ...)` with the right line number.
- Unit test: a composite that does `if x == other:` → raises.
- Unit test: a composite that iterates `for item in x.items:` →
  raises.
- Unit test: Pipeline, Parallel, Switch, ReAct, Talker, PRReviewer —
  every existing composite must still build cleanly. Zero regressions.
  This is the acceptance bar.
- Unit test: the error message contains the filename and line.
- `scripts/verify.sh` green.

---

## Out of scope

- Detecting payload-branching *inside leaves*. Leaves are
  pure computations and legitimately read fields — VISION §5.3 spells
  this out explicitly ("Only composites get the payload-branch guard").
- Runtime (post-build) validation. Once built, composites run for
  real with real payloads; no further checking needed.
- Rewriting composites the library ships to remove borderline cases.
  If a legitimate composite has to branch on payload, its author can
  annotate the forward with a `# operad: payload-read-ok` hint or,
  cleaner, refactor to route via a `Switch` — this is the intended
  API.

---

## Design notes

- Think of this as `torch.fx`-lite: a narrow tracer that flags a
  specific class of mistake. It should be boring to review.
- Keep the sentinel subclass cached per `input` type — do not rebuild
  it on every `forward` call during trace.
- The `traceback.extract_stack()` walk must be resilient: if the
  composite's `forward` was defined in a Jupyter cell or exec'd
  string, filename lookup may fail. Degrade gracefully — emit the
  error without the line info rather than crash.
- Watch the fallback AST scan for composites whose `forward` is
  wrapped in a decorator. `inspect.getsource(func)` returns the
  decorated source; the scan should still find the inner `if` etc.,
  but test for it.
