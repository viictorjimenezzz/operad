# Feature · `Trace` — runtime capture, cost estimation, replay

A first-class `Trace` object that captures one full run of an agent
graph. Underpins two features at once:
- **Cost/token estimator attached to the trace** (not the agent).
- **Trace replay against a new metric** — re-score a stored trace
  without re-running any LLM.

**Covers Part-3 items.** #5 (cost estimator relocated to the Trace),
#12 (trace replay; make it super nice).

---

## Required reading

`METAPROMPT.md`, `ISSUES.md`, `VISION.md` §6–§7, and:
- `.conductor/feature-operad-output.md` — the Trace is a sequence of
  `OperadOutput`s keyed by path. **Hard dependency.**
- `.conductor/2-C-observers.md` — the Trace is populated by an
  observer.
- `.conductor/2-D-metrics-evaluation.md` — replay re-scores against
  metrics from this package.

---

## Proposal sketch

### `Trace` object

```python
class TraceStep(BaseModel):
    agent_path: str
    output: OperadOutput[Any]    # Any for deserialisation; typed via path→schema map

class Trace(BaseModel):
    run_id: str
    graph: AgentGraph            # or a dumped form; see below
    steps: list[TraceStep]       # in invocation order
    root_input: dict[str, Any]   # Pydantic-dumped
    root_output: dict[str, Any]  # Pydantic-dumped
    started_at: float
    finished_at: float

    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path, *, type_registry: TypeRegistry | None = None) -> "Trace": ...
```

### How a Trace is created

- A `TraceObserver` subscribes to Stream C's observer events.
- It accumulates `OperadOutput`s into `steps` as `on_event(end)`
  fires.
- At the root's final `end` event, it snapshots the run into a
  `Trace` and optionally writes it to disk (NDJSON-of-steps or a
  single JSON file — choose based on downstream tooling).

### Cost estimator

Free function in `operad/runtime/cost.py`:

```python
def cost_estimate(trace: Trace, *, pricing: dict[str, Pricing] | None = None) -> CostReport:
    """Sum prompt/completion tokens across a trace; convert to USD.

    Uses per-step `OperadOutput.prompt_tokens` / `completion_tokens`
    when populated; otherwise falls back to a simple char/4 heuristic
    on the rendered prompt text.
    """
```

Pricing is a dict keyed by `"<backend>:<model>"`; ship a tiny starter
table for openai and llamacpp (free), with a clear "bring your own
table" story.

### Trace replay

Free function in `operad/runtime/replay.py`:

```python
async def replay(
    trace: Trace,
    metrics: list[Metric],
    *,
    expected: dict[str, Out] | None = None,
) -> EvalReport:
    """Re-score a recorded trace against new metrics.

    Uses per-step `response` payloads from the trace; does NOT
    re-invoke any agent or LLM. For metrics that need an `expected`,
    pass a mapping from agent_path → expected Out.
    """
```

The big win: iterate on evaluation criteria at essentially zero cost.

---

## Research directions

- **AgentGraph serialisation.** `Trace.graph` needs to round-trip.
  `AgentGraph` is a dataclass with `type` objects — serialisation
  requires replacing types with their qualified names and a
  `TypeRegistry` for `load`. Investigate whether `to_json` in
  `operad/core/graph.py` is sufficient or if you need a richer dump.
- **Typed deserialisation of `OperadOutput[Out]`.** A saved trace on
  disk has `response` as a dict. Rehydrating to the user's `Out`
  type needs the `Out` class — either carry its qualified name on
  the trace, or require the caller to pass a `{path: Out_cls}` map.
  Pick the cheaper and clearer path.
- **Partial traces.** What if a run errored mid-way? The `TraceStep`
  should carry `error` too — probably just copy `OperadOutput.error`
  if `feature-operad-output.md` ships one, or add an `error: str | None`.
- **Storage format.** Single JSON? NDJSON per step with a header?
  For small runs, single JSON is fine; for long-running
  AutoResearcher-style runs, NDJSON + tail-reading matters.
- **Cost heuristic.** `char_count // 4` is notoriously inaccurate for
  non-English and for code. Document the heuristic's limitations
  and let users provide a `tokenizer: Callable[[str], int]`.

---

## Integration & compatibility requirements

- **Hard dependency on `OperadOutput`.** Do not start until
  `feature-operad-output.md` is merged or its shape is frozen.
- **Trace is populated via observer events**, not by editing
  `Agent.invoke` directly. Reuse Stream C's hook point.
- **`run_id` matches `OperadOutput.run_id` and observer events.**
  Single source of truth.
- **`evaluate` and `replay` share `EvalReport`.** Reuse Stream D's
  definition; do not invent a parallel type.
- **No forced serialisation dep.** Use stdlib `json`. Pickle is
  acceptable for a dev-only helper but not the default.
- **Document in `CLAUDE.md`** that `Trace` is the reproducibility
  artefact for any production run.

---

## Acceptance

- `uv run pytest tests/` green.
- Running a ReAct once with a `TraceObserver` produces a non-empty
  `Trace` with four `TraceStep`s.
- `Trace.save(path); Trace.load(path)` round-trips byte-identically
  after normalisation.
- `replay(trace, [ExactMatch(...)])` returns an `EvalReport` without
  touching any LLM — assert on no-network via a conftest helper.
- `cost_estimate(trace)` returns sensible numbers given a small
  pricing table.

---

## Watch-outs

- Don't conflate `Trace` with `AgentGraph`. The graph is static
  topology; the trace is a dynamic run.
- Large traces can grow: truncate or stream when a single run has
  >1000 steps.
- For replay: a metric that *calls an LLM* (e.g. `RubricCritic`) is
  NOT zero-cost. Document this — replay is zero-cost only for
  deterministic metrics.
- Test the replay-of-a-replay case: does a trace re-scored with new
  metrics remain valid input for another re-score? It should.
