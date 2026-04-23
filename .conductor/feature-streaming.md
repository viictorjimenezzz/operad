# Feature · Streaming support

**Addresses.** E-8 (ISSUES.md) + `TODO_STREAMING` in `missing.py`.

strands exposes token-level streaming; operad swallows it by awaiting
the final result. Add a first-class streaming path: a `stream: bool`
toggle on `Configuration`, an `Agent.stream(x)` async-iterator, and
a new observer event kind so dashboards can show mid-run state.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-8.
- `operad/core/agent.py`, `operad/runtime/observers/base.py`.
- strands docs / source for streaming API shape.

---

## Proposal

### Configuration

```python
stream: bool = False   # default off; opt-in
```

### New observer event kind

`AgentEvent.kind` gains `"chunk"`:

```python
AgentEvent(
    run_id, path, "chunk",
    input=x, output=None, error=None,
    started_at=chunk_started, finished_at=None,
    metadata={"chunk_index": i, "text": piece, ...},
)
```

Observers that don't care (`JsonlObserver`) still log them; dashboards
(`RichDashboardObserver`) update the running agent's line in-place.

### `Agent.stream(x)`

New method yielding the in-flight chunks plus a final `OperadOutput`:

```python
async def stream(
    self, x: In
) -> AsyncIterator[ChunkEvent | OperadOutput[Out]]:
    """Yield chunk events while the model generates; terminate with
    the full `OperadOutput`.

    Equivalent to `await self.invoke(x)` if the backend does not
    support streaming or `Configuration.stream=False` — in which case
    exactly one `OperadOutput` is yielded.
    """
```

`ChunkEvent` is a tiny Pydantic model or a plain dataclass:
`{text: str, index: int, agent_path: str}`.

Existing `invoke`/`__call__` remain unchanged in shape: they still
return a single `OperadOutput` (they internally consume the stream
when `stream=True` and return the final envelope).

### strands dispatch

The default leaf `forward` currently calls
`super().invoke_async(..., structured_output_model=...)`. Under
streaming, switch to strands' streaming API (likely `stream_async`
or similar — verify). Wire each token into the `"chunk"` event. When
streaming ends, parse accumulated text with `self.output.model_validate_json`
(matches the `structuredio=False` path from
`.conductor/feature-structuredio.md` — coordinate with that stream).

---

## Required tests

`tests/test_streaming.py`:

1. With `stream=False`: `agent.stream(x)` yields exactly one
   `OperadOutput`. Same typed output as `await agent(x)`.
2. With `stream=True` and a mocked strands streamer that emits
   3 chunks: 3 `ChunkEvent`s yielded, then one final `OperadOutput`.
3. Observers receive one `"chunk"` event per mid-run token piece
   and one terminal `"end"` event.
4. Structured-output parsing still works when the model's streamed
   text round-trips to valid JSON for `Out`.

---

## Scope

- Edit: `operad/core/config.py` (new field).
- Edit: `operad/core/agent.py` (`stream` method, dispatch in
  `forward`).
- Edit: `operad/runtime/observers/base.py` (`"chunk"` kind,
  typing).
- Edit: `operad/runtime/observers/rich.py` (in-place text update).
- Edit: `operad/runtime/observers/jsonl.py` (safe fallthrough).
- New: `tests/test_streaming.py`.

Do NOT:
- Change the return type of `invoke`/`__call__`. Streaming is opt-in
  through `.stream()`.
- Couple streaming to the observer registry; users calling
  `.stream()` should get chunks directly even with no observer
  registered.

---

## Acceptance

- `uv run pytest tests/` green.
- New test asserts end-to-end streaming with a mocked strands
  streamer.
- `RichDashboardObserver` updates the agent's status line
  as chunks arrive (manual verification — no automated display test).
- `README.md` gains a "Streaming" section showing `async for`.

---

## Watch-outs

- Coordinate with `.conductor/feature-structuredio.md` — parsing the
  final accumulated text requires schema-driven validation, which
  lives in that stream's `structuredio=False` path. If feature-structuredio
  hasn't merged, implement a minimal local parser and refactor later.
- Streaming + retry is complex. For v1, if a retry fires mid-stream,
  re-emit the whole stream under a new `run_id`. Document this.
- Not every backend supports streaming — bedrock via strands may not.
  Gracefully fall back: if backend doesn't support, yield one final
  `OperadOutput` and emit no `"chunk"` events.
