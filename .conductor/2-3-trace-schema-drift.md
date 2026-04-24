# 2 · 3 — Trace schema-drift detection

**Addresses.** C5 (warn on output-schema drift during `Trace.load`; refuse
`replay` unless `strict=False`).

**Depends on.** 1-1-restructure.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §6 (Trace as the reproducibility artefact).
- `operad/runtime/trace.py` — `Trace`, `TraceStep`, `TraceObserver`.
- `operad/runtime/replay.py` — current module-level `replay(trace, metrics,
  …)` function.
- `operad/core/output.py` — `OperadOutput.hash_output_schema`,
  `hash_schema(cls)`. Each `TraceStep.output` already carries a
  `hash_output_schema` field populated at invoke time.
- `operad/utils/errors.py` — `BuildError`, `BuildReason` literal.

---

## Proposal

A stored `Trace` carries the hash of each step's `Output` schema at capture
time. Between capture and replay the agent's `Output` can evolve (a field
rename, a new required attribute, a different enum member). Today that
drift is silent: `replay` happily rescoring against mismatched shapes
produces confusing metric errors or, worse, false-positive passes.

This PR adds two things:

1. **`Trace.load` warns** when any step's `hash_output_schema` doesn't
   match the hash of that agent's *current* `Output` class, **if** a
   reference agent is supplied. No agent ⇒ no warning (backwards-safe
   default for callers that only want the payload on disk).
2. **`Trace.replay(agent, metrics, *, strict=True)` method** — a thin
   method that wraps the existing `runtime.replay.replay(…)` function and
   adds a drift gate. If any step's `hash_output_schema` differs from the
   corresponding leaf's current `hash_schema(output)`, raise
   `BuildError("schema_drift", …)`. Passing `strict=False` downgrades the
   gate to a logged warning and annotates the returned `EvalReport` with
   a `schema_drift` flag.

### API

```python
# operad/runtime/trace.py

class Trace(BaseModel):
    ...

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        type_registry: TypeRegistry | None = None,
        agent: "Agent[Any, Any] | None" = None,   # NEW
    ) -> "Trace":
        """Load a trace. If `agent` is supplied, warn on output-schema drift."""

    async def replay(
        self,
        agent: "Agent[Any, Any]",
        metrics: list["Metric"],
        *,
        strict: bool = True,
        expected: "BaseModel | None" = None,
        predicted_cls: "type[BaseModel] | None" = None,
        expected_cls: "type[BaseModel] | None" = None,
    ) -> "EvalReport":
        """Re-score this trace against `agent`'s metrics.

        If any step's `hash_output_schema` differs from the current
        schema hash for the same agent path, raise `BuildError(
        "schema_drift", …)`. Pass `strict=False` to downgrade the gate
        to a warning + `schema_drift=True` flag on the returned report.
        """
```

### Drift detection helper

```python
# operad/runtime/trace.py (private)

def _collect_drift(trace: Trace, agent: "Agent[Any, Any]") -> list[tuple[str, str, str]]:
    """Return a list of (agent_path, recorded_hash, current_hash) for each
    step whose recorded `hash_output_schema` does not match the agent
    subtree's current schema at the same path. Empty when no drift.
    """
```

Implementation uses the agent tree's `_children` walk keyed by `agent_path`
(the path strings already present on each `TraceStep`). For steps whose
path no longer resolves (a renamed sub-agent), treat that as drift with
`current_hash = ""`.

### `BuildReason` extension

Add exactly one new literal to `operad/utils/errors.py`:

```python
BuildReason = Literal[
    "not_built",
    "prompt_incomplete",
    "input_mismatch",
    "output_mismatch",
    "trace_failed",
    "payload_branch",
    "router_miss",
    "schema_drift",   # NEW
]
```

No other file in this PR touches `errors.py`. (2-2 only edits `__str__`;
2-3 only edits the literal.) If the two PRs race, the merge is trivial —
both sides are additive, one line each.

### Warning channel

Use `warnings.warn(..., category=UserWarning, stacklevel=2)` for the
non-strict path (matches how `pytest.warns` picks it up in tests). No
`print`, no `logging`.

### `runtime/replay.replay` unchanged

Keep the module-level `replay(trace, metrics, …)` untouched for users who
don't care about drift. `Trace.replay` is a richer sibling that layers
the drift gate; it calls into `runtime.replay.replay` internally once
the gate passes.

---

## Required tests

`tests/test_trace_schema_drift.py` (new):

1. **`load` warns on drift.**
   - Build a `FakeLeaf` with `Output = AnswerV1`, capture a trace.
   - Mutate the leaf class to `Output = AnswerV2` (one extra field).
   - Call `Trace.load(path, agent=mutated_agent)` under
     `pytest.warns(UserWarning, match="schema_drift")`.
   - Without the `agent=` argument, no warning is emitted.

2. **`replay(strict=True)` raises.**
   - Same setup as above. `await trace.replay(mutated_agent, [ExactMatch()])`
     raises `BuildError` with `reason == "schema_drift"`.

3. **`replay(strict=False)` proceeds.**
   - `await trace.replay(mutated_agent, [ExactMatch()], strict=False)`
     returns an `EvalReport`; `report.summary["schema_drift"] == 1.0`
     (flag convention: 1.0 means drift detected, 0.0 clean).

4. **Composite-path drift.**
   - Pipeline of two FakeLeaves; mutate only the second stage's Output.
   - Drift report names `Root.stage_1` (or whichever path the second
     stage occupies) exactly; other paths are clean.

5. **No-drift baseline.**
   - Trace, reload, replay — same agent instance. No warnings, no raise,
     `summary["schema_drift"]` is 0.0 (or simply absent).

All tests offline; use `FakeLeaf`. No network.

---

## Scope

**New files.**
- `tests/test_trace_schema_drift.py`.

**Edited files.**
- `operad/runtime/trace.py` — add `agent=` keyword to `Trace.load`, add
  `Trace.replay` method, add private `_collect_drift` helper.
- `operad/utils/errors.py` — add the `"schema_drift"` literal to
  `BuildReason`. No other change.

**Must NOT touch.**
- `operad/core/agent.py` — owned by 2-1.
- `operad/core/output.py` — already exports `hash_schema`/
  `hash_output_schema`; just consume them.
- `operad/runtime/replay.py` — leave the module-level `replay` alone;
  `Trace.replay` delegates to it unchanged.
- Any other file in Wave 2.

---

## Acceptance

- `uv run pytest tests/test_trace_schema_drift.py` green.
- `uv run pytest tests/` green (full suite).
- `Trace.load(path)` without an `agent` behaves exactly as before.
- `Trace.replay` with a drift-free agent matches the module-level
  `replay`'s output (same summary keys, same scores).
- `BuildError` with `reason="schema_drift"` stringifies cleanly (the
  2-2 mermaid footer does NOT fire for this reason — it's not graph-local).

---

## Watch-outs

- **`BuildReason` coordination with 2-2.** 2-2 changes `BuildError.__str__`
  and leaves the literal tuple alone. 2-3 changes the literal tuple and
  leaves `__str__` alone. Additive merge.
- **Composite-path resolution.** `TraceStep.agent_path` is a dotted
  string like `"Root.stage_1"`. Map it to a leaf by splitting on `.` and
  walking `_children` by attribute name. If a component at that path is
  itself a composite (e.g. a `Parallel` node mid-graph), it has no
  `Output` to hash — skip those steps.
- **`_Empty` placeholder steps.** Error steps carry a `_Empty` response
  with no meaningful `hash_output_schema`. Skip steps where
  `step.output.hash_output_schema == ""`.
- **Cross-version traces.** A trace captured before this PR has the same
  `hash_output_schema` field populated (existing behaviour — line 656 of
  `agent.py`). No migration required.
- **Warning visibility under pytest.** `pytest` filters `UserWarning` by
  default in some configs. The test uses `pytest.warns` which forces
  capture; no `warnings.simplefilter` mutation in library code.
- **`Metric` import.** Avoid a runtime cycle: import `Metric` and
  `EvalReport` inside `Trace.replay`'s body (both live in
  `operad/benchmark/…` after 2-5, or `operad/metrics/` + `operad/eval.py`
  pre-2-5). This PR is agnostic — it uses `TYPE_CHECKING` imports for
  the signature and local imports for the body.
