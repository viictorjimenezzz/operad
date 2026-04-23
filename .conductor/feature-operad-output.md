# Feature · `OperadOutput` — canonical return shape

A typed envelope for the result of every agent call, carrying the
user's `Out` alongside reproducibility and run metadata. Foundational:
the `Trace` feature (`feature-trace.md`) and the cost estimator rely
on it.

**Covers Part-3 item.** #9 (reproducibility metadata) reshaped into a
first-class return type with `hash_*` attributes clustered by prefix.

---

## Required reading

`METAPROMPT.md`, `ISSUES.md`, `VISION.md` §5–§6, and:
- `.conductor/1-A-core-correctness.md` — touches the `Agent.invoke`
  return path; coordinate if Stream A is not yet merged.
- `.conductor/2-C-observers.md` — observer events should quote fields
  from the `OperadOutput`, not duplicate them.
- `.conductor/feature-trace.md` — primary downstream consumer.

---

## Proposal sketch

### Shape

```python
class OperadOutput(BaseModel, Generic[Out]):
    """Envelope returned by every Agent invocation.

    `response` holds the user's typed output; `hash_*` fields cluster
    reproducibility metadata; remaining fields describe the run.
    """

    response: Out

    # Reproducibility (hash_*, grouped by prefix)
    hash_operad_version: str
    hash_python_version: str
    hash_model: str           # stable hash of Configuration
    hash_prompt: str          # hash of rendered system+user messages
    hash_graph: str           # hash of AgentGraph (structural)
    hash_input: str           # hash of the input payload
    hash_output_schema: str   # hash of Out's JSON schema

    # Run metadata
    run_id: str
    agent_path: str
    started_at: float
    finished_at: float
    latency_ms: float

    # Usage (optional; populated when the backend exposes it)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
```

All `hash_*` fields use the same hash function — SHA-256 truncated to
~16 hex characters is a sensible default. Input for the hash: stable
JSON (`json.dumps(..., sort_keys=True)` on the Pydantic dump).

### API choice: two paths to explore

**Option 1 — breaking, cleaner.** Change `Agent.invoke` / `__call__`
to return `OperadOutput[Out]`. Composites unwrap `.response` when
chaining children. External callers migrate to `out.response.field`.

```python
async def invoke(self, x: In) -> OperadOutput[Out]:
    ...
```

Pipeline becomes:
```python
async def forward(self, x):
    current = x
    for stage in self._stages:
        current = (await stage(current)).response
    return current  # forward still returns Out, invoke re-wraps
```

**Option 2 — non-breaking, busier.** Keep `__call__(x) -> Out`; add
`Agent.trace_call(x) -> OperadOutput[Out]` for observer/trace
consumers. Leaves more code paths.

The user indicated preference for `OperadOutput` being *the* return
shape → Option 1 is aligned, but requires:
- Updating every test that does `out.answer` to `out.response.answer`.
- Updating existing composites (Pipeline, Parallel) to unwrap.
- Updating algorithms (BestOfN, VerifierLoop, etc.) to unwrap.
- Clear docs + a migration note in `CLAUDE.md`.

**Investigate both options, propose one with rationale, then
implement.** If Option 1, do it in one PR — partial migration is
worse than either endpoint.

---

## Research directions

- **Pydantic generic return types.** Pydantic v2 handles
  `OperadOutput[SomeOut]` but the generic resolves to `BaseModel` in
  some paths; verify it serialises and validates as expected.
  Especially important for `BestOfN` / `VerifierLoop` whose outputs
  are typed against the user's `Out`.
- **Hash stability across runs.** Pydantic's `model_dump_json`
  orders keys by field declaration; test that the same input twice
  produces the same `hash_input`.
- **Token / cost population.** Strands exposes some usage info
  on the result object — inspect `result.metrics` / equivalents in
  each backend adapter and thread into `OperadOutput`.
  This is partial; Stream D's `cost.py` can enrich later.
- **`run_id` correlation.** Should match Stream C's `_RUN_ID`
  contextvar so observer events and `OperadOutput.run_id` agree.
- **`agent_path` resolution.** The tracer stacks attribute names
  (`build.py`); at runtime, Stream C's `_PATH_STACK` does the same.
  `OperadOutput.agent_path` should use the same scheme.

---

## Integration & compatibility requirements

- **Coordinate with Stream C.** Observer events carry `run_id` and
  `agent_path`; `OperadOutput` uses the same. A single source of
  truth — define the contextvars in one module and import from both.
- **Coordinate with Stream A.** If A hasn't merged, flag the return-
  type change in your PR description; it is likely to conflict.
- **Coordinate with Stream F.** `BestOfN`, `VerifierLoop`, and
  `Evolutionary` all handle outputs of child agents — they must
  unwrap `.response` when chaining.
- **Coordinate with Stream K.** The canonical examples must show
  `out.response.field`, not `out.field`. Update them in the same
  PR.
- **Configuration hash.** `Configuration` has `extra="forbid"` and is
  a Pydantic model; `hash_model` = hash of its `model_dump_json`.
  Exclude `api_key` from the hash (secret).

---

## Acceptance

- `uv run pytest tests/` green after the migration.
- The same input run twice produces identical `hash_input`,
  `hash_prompt`, `hash_graph`, `hash_output_schema`.
- Changing the agent's `task` changes `hash_prompt` but not
  `hash_graph`.
- Mermaid / graph exports are unaffected.
- Observer events and `OperadOutput` share the same `run_id`.

---

## Watch-outs

- Do NOT put the `api_key` in any hash.
- Do NOT change `forward(x) -> Out` — only `invoke` / `__call__`
  wrap.
- Leaf-root `build()` semantics (see ISSUES §A-3) interact with the
  return type; test this explicitly.
- Keep the `hash_*` cluster together in the class body for readability.
- Truncated SHA-256 is for display, not cryptographic use. Document
  this.
