# 2 · 1 — Agent feature bundle

**Addresses.** C1 (`hash_content`), C2 (`forward_in` / `forward_out`),
C3 (`validate`), O2 (`explain`), O6 (`__rich__`), E1 (`>>`), E3
(`summary`).

All changes land in **one PR** to `operad/core/agent.py` so the Agent
class only has a single editor in Wave 2.

**Depends on.** 1-1-restructure (must be merged first).

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §A (payload-branching footgun stays out of
  scope here), `VISION.md` §3–§4.
- `operad/core/agent.py` end to end (especially the post-1-1 invoke/stream
  consolidation).
- `operad/core/state.py` — `AgentState` is the input to `hash_content`.
- `operad/runtime/trace.py` — `TraceObserver` powers `explain`.
- `operad/agents/pipeline.py` — `Pipeline` is what `>>` returns.

---

## Proposal

Seven orthogonal additions, all methods/properties on `Agent`. Each is
small on its own; the bundling is for conflict-free Wave-2 parallelism.

### C1 · `hash_content` property

```python
@property
def hash_content(self) -> str:
    """16-hex-char SHA-256 over the agent's declared state.

    Enables content-addressable grouping: two agents with the same
    `hash_content` produce the same rendered system prompt for every
    leaf, regardless of object identity. Used by `Experiment` (3-3) for
    cache keys and for "is this the same agent as run #47?" equality.
    """
    from ..utils.hashing import hash_json
    return hash_json(self.state().model_dump(mode="json"))
```

Stable across `.build()` (build does not mutate declared state). Changes
after any mutation op (`AppendRule`, `EditTask`, …) because those
mutate `role`/`task`/`rules`/`examples`/`config` and therefore `state()`.

### C2 · `forward_in` / `forward_out` hooks

Default pass-through; subclasses override to redact, truncate, repair:

```python
def forward_in(self, x: In) -> In:
    """Runs before `forward`. Override to mutate or redact `x`."""
    return x

def forward_out(self, x: In, y: Out) -> Out:
    """Runs after `forward`. Override to repair or moderate `y`."""
    return y
```

The invoke envelope (1-1's `_invoke_envelope` or equivalent) calls them
around `forward`:

```python
x = self.forward_in(x)
y = await self.forward(x)
y = self.forward_out(x, y)
```

Hooks run under the same retry/streaming/observer path; no new events
are emitted.

### C3 · `validate(x)` — the only pre-flight

```python
def validate(self, x: In) -> None:
    """Raise if this agent cannot accept `x`.

    Checks `_built` (raises `BuildError("not_built", ...)`) then the
    input type (raises `BuildError("input_mismatch", ...)`). This is
    the single source of truth for input validation — remove the
    inline checks previously in `invoke` / `stream` and call this
    method from the envelope helper instead.
    """
    if not self._built:
        raise BuildError("not_built", "call .build() before .invoke()",
                         agent=type(self).__name__)
    if not isinstance(x, self.input):
        raise BuildError(
            "input_mismatch",
            f"expected {self.input.__name__}, got {type(x).__name__}",
            agent=type(self).__name__,
        )
```

**Mandatory follow-through.** Remove the old inline checks that 1-1 left
in `_invoke_envelope` (the `if not self._built` and
`if not isinstance(x, self.input)` blocks). Replace with `self.validate(x)`.
Grep the repo for any other ad-hoc `isinstance(x, self.input)` call outside
tests — there should be none after this PR. The output-side check
(`isinstance(y, self.output)`) stays inline; it's not an input pre-flight.

### O2 · `explain(x)` — chain-of-thought narration

Runs `x` through the agent with a temporary `TraceObserver` and prints,
per leaf: its scratchpad (auto-injected if the leaf's `Output` schema
doesn't already have one) and its final response.

```python
async def explain(self, x: In) -> None:
    """Run `x`, print scratchpad + output for every leaf in the trace.

    If a leaf's `Output` schema has no `scratchpad: str` field,
    temporarily subclass `Output` to prepend one. The model emits
    scratchpad first, then the rest of the structured response
    (DSPy-style CoT). Prints to stdout — no logging framework.
    """
    from ..runtime.trace import Trace, TraceObserver
    from pydantic import create_model, Field

    # 1. Walk the tree. For each default-forward leaf whose Output lacks
    #    scratchpad, swap `self.output` for an augmented subclass.
    # 2. Register a TraceObserver scoped to this call.
    # 3. await self.invoke(x)
    # 4. For every step in the captured trace, print:
    #        === {agent_path} ===
    #        scratchpad: ...
    #        output: ...
    # 5. Restore the original `self.output` on each swapped leaf.
```

Helper:

```python
def _augmented_output(out_cls: type[BaseModel]) -> type[BaseModel]:
    if "scratchpad" in out_cls.model_fields:
        return out_cls
    fields = {
        "scratchpad": (str, Field(description="Think step-by-step here first.")),
    }
    for name, f in out_cls.model_fields.items():
        fields[name] = (f.annotation, f)
    return create_model(f"{out_cls.__name__}WithScratchpad", **fields,
                        __base__=BaseModel)
```

Constraints:
- Parent implementation works for every `Agent` without subclass
  overrides. No "The Reasoner thought…" prose.
- Swaps are thread-local and fully restored in a `finally` block.
- If the user already rendered the prompt (`format_system_message`) and
  cached it in `build()`, the swap must re-render for that invocation
  (call site should re-init strands for the augmented leaf *or* defer
  the swap to `format_user_message`'s output-schema block — see
  watch-outs).

### O6 · `__rich__`

```python
def __rich__(self):
    """Rich rendering — structured tree for `rich.print(agent)`."""
    from rich.tree import Tree
    ...
```

Renders: class name, I/O type names, role preview (first 60 chars),
leaf count (walk `_children` recursively with id-dedup), graph hash
(short) when `_built`, backend + model when `config` is set. Handles
unbuilt agents gracefully. ~20 LOC. `rich` is already an optional
extra (`[observers]`); import lazily inside the method.

### E3 · `summary()`

```python
def summary(self) -> str:
    """One-paragraph overview of this agent (post-build if available)."""
```

Format:

```
{ClassName}: {n_leaves} leaves, {n_composites} composites, hash_content={...}
  graph_hash={short}  backend={...}  model={...}
```

If `_graph` is unset, skip graph hash. If no runs have been captured yet
(no cached latencies), skip the latency fragment. Keep it to one
paragraph, `print(agent.summary())`-friendly.

### E1 · `__rshift__` / `>>`

```python
def __rshift__(self, other: "Agent[Any, Any]") -> "Pipeline":
    from ..agents.pipeline import Pipeline
    if isinstance(self, Pipeline):
        return Pipeline(*self._stages, other)
    return Pipeline(self, other)
```

`a >> b` → `Pipeline(a, b)`. `a >> b >> c` flattens into
`Pipeline(a, b, c)` rather than `Pipeline(Pipeline(a, b), c)`. Dict
syntax already works for `Parallel` (constructor accepts a mapping);
leave that alone.

---

## Required tests

`tests/test_agent_features.py`:

1. **hash_content stability.** Two freshly built `FakeLeaf` instances with
   identical state have the same `hash_content`. Mutating `rules` via
   `AppendRule` changes it. Calling `.build()` again does not.
2. **forward_in/forward_out.** Subclass a FakeLeaf to upper-case its
   input string; assert `forward` sees the upper-cased value via an
   injected `_last_seen` attribute.
3. **validate.**
   - `agent.validate(x)` on an unbuilt agent raises `BuildError("not_built", ...)`.
   - On a built agent with wrong-type input, raises
     `BuildError("input_mismatch", ...)`.
   - `await agent.invoke(x)` on an unbuilt agent raises exactly once at
     the `validate` call (grep confirms no duplicate `isinstance` check
     remains).
4. **explain.** Using a FakeLeaf wrapping a cassette-free stub that
   returns a structured response, call `await agent.explain(x)` and
   assert capsys captures both a `scratchpad:` line and an `output:`
   line for each leaf.
5. **__rich__.** `from rich.console import Console; Console().print(agent)`
   does not raise and produces a tree containing "leaves" and "hash".
6. **summary.** Pre-build returns a string without the graph-hash fragment;
   post-build includes it.
7. **__rshift__.** `a >> b` is a Pipeline with two stages; `a >> b >> c`
   has three stages (flat).

All tests use `FakeLeaf` from `tests/conftest.py` — offline, no network.

---

## Scope

**Files owned (editable).**
- `operad/core/agent.py`.
- `operad/core/example.py` (only if an explain-related `Example` change
  is needed; usually untouched).
- `tests/test_agent_features.py` (new).

**Must NOT touch.**
- `operad/core/build.py`, `operad/core/graph.py` — owned by 2-2.
- `operad/core/config.py` — owned by 3-4.
- `operad/core/output.py`, `operad/utils/errors.py` — owned by 2-3 (adds
  `schema_drift` reason there).
- `operad/runtime/trace.py` — owned by 2-3.
- `operad/runtime/observers/*` — owned by 2-8.
- `operad/utils/cassette.py` — owned by 2-9.
- `operad/runtime/slots.py` — owned by 2-11.
- Any other wave-2 file outside `operad/core/agent.py`.

---

## Acceptance

- Every test in `tests/test_agent_features.py` green.
- `uv run pytest tests/` green.
- `agent.invoke` and `agent.stream` route input validation exclusively
  through `self.validate(x)` — a grep for `isinstance(x, self.input)` in
  `operad/core/agent.py` returns exactly zero hits outside `validate`.
- `agent.explain(x)` works offline with a FakeLeaf.
- `rich.print(agent)` renders without error.

---

## Watch-outs

- **explain + structured output.** Swapping `self.output` alone may not
  flow into strands' structured-output mode because strands cached it at
  build time. Two reasonable patterns: (a) monkey-patch
  `format_system_message` to render the augmented schema and call
  `super().invoke_async(..., structured_output_model=augmented_cls)`
  directly; or (b) re-init strands for the swapped leaf temporarily.
  Option (a) is lighter — prefer it. Document the choice in a brief
  comment.
- **Example untouched.** Keep `Example`'s home in `core/example.py` (from
  1-1). Don't move it again.
- **`hash_content` uses `state()`.** If `state()` changes semantics
  later (e.g. includes child order), the hash changes accordingly. For
  this PR the current `state()` shape is fine.
- **`>>` on a Pipeline** must return a new Pipeline, not mutate the
  left-hand side. `Pipeline(*self._stages, other)` creates a fresh
  instance.
- **forward_in/forward_out ordering.** Both run *inside* the retry loop
  so a failed attempt re-runs the hooks. If that is wrong for some use
  case, the fix is a future orthogonal brief — don't pre-optimise now.
