# 4-1 Forward-hook indicators + streaming chunk replay

## Scope

Two distinct but adjacent enrichments to the agent view:

1. Surface `forward_in` / `forward_out` hook overrides on the
   agent edges so users can see at a glance which leaves wrap a
   pre/post hook (often used for redaction, repair, moderation).
2. Add a streaming-chunk replay mode to invocation detail —
   token-by-token playback of how an output was generated, using
   the buffered `chunk` events.

### You own

- `apps/frontend/src/components/agent-view/graph/agent-edge-popup.tsx`
  (extend) — add a "hooks" indicator section.
- `apps/frontend/src/components/agent-view/graph/hook-badge.tsx`
  (new) — small badge component showing "forward_in" /
  "forward_out" override status.
- `apps/frontend/src/components/agent-view/insights/`
  - `chunk-replay.tsx` (new) — token-by-token playback panel.
  - Extend `agent-insights-row.tsx` to mount it conditionally
    (only when at least one invocation has chunk events).
- `apps/dashboard/operad_dashboard/agent_routes.py` (extend) —
  ensure `/runs/{id}/agent/{path}/meta` returns
  `forward_in_overridden` / `forward_out_overridden` (1-3 already
  delivers this; verify and use).

### Depends on

- 1-3's `meta` endpoint (already includes the hook flags per
  brief).
- 2-2's edge popup (extend cleanly).
- 2-4's insights row (extend cleanly).
- The dashboard's existing chunk-event ingestion (chunks are in
  the event buffer with `kind == "chunk"`).

### Out of scope

- Implementing the hook detection in operad core — already in
  place (compare `type(agent).forward_in is not Agent.forward_in`).
- The full replay-as-an-experiment feature (4-3 owns).

---

## Vision

### Hook indicators

In the agent edge popup, render a small "hooks" row under the
class name:

```
[ forward_in ]  redacts input        ← green chip when present
[ forward_out ] repairs output       ← gray when not overridden
```

Hover the chip → tooltip with a one-line explanation pulled from
the agent class's docstring (if available — query
`/runs/{id}/agent/{path}/meta` for `forward_in_doc`,
`forward_out_doc` if you want, but fall back to a generic
"input is transformed before being sent to the model").

### Streaming chunk replay

A small "Replay" panel inside the insights row that's only
visible when:

- At least one invocation in the buffer has `chunk` events for
  this agent path.

Panel UX:

- A play / pause / reset button row.
- A scrubber bar with one tick per chunk.
- The text area below renders chunks progressively as `play` is
  pressed, simulating how the model streamed in real-time.
- "Speed" toggle: 0.5x, 1x, 2x, fast (no delay).
- Show the input that produced this stream, and the final
  envelope hash to anchor it.

---

## Implementation pointers

- Reflect on which invocations have chunk events using
  `useEventBufferStore`. Group chunks by `(run_id, invocation_id,
  agent_path)`.
- Replay timing: store the `started_at` of each chunk relative to
  the first; on play, schedule `setTimeout` to render each chunk
  at the appropriate elapsed time (or immediate if "fast" mode).
- Hook detection is pure flag → render. Don't ship an icon if the
  meta endpoint didn't include the flag (defensive).
- Pull `forward_in` / `forward_out` docstrings server-side: in
  1-3's `meta` route, do `inspect.getdoc(type(agent).forward_in)`
  for both. Add fields `forward_in_doc` / `forward_out_doc` —
  document this addition in your PR.

---

## Polish targets

- Replay should feel real. The cursor blinks. Pause restores the
  caret. Fast mode renders instantly.
- Hook chips should be unmissable when active and visually
  background when not. Consider a subtle "?" link to the operad
  docs explaining what these hooks do.
- Multiple invocations with chunks → a small dropdown to pick
  which invocation to replay.

---

## Be creative

- A "diff stream" mode where two invocations' streams are played
  side by side, useful for prompt-tuning A/B comparisons.
- "Token-by-token" view that shows the underlying token IDs
  alongside the rendered text (if the backend exposes them).
- Export the replay as a GIF or a structured NDJSON.

---

## Verification

```bash
pnpm -C apps/frontend test
pnpm -C apps/frontend typecheck
uv run pytest apps/dashboard/tests/ -q
make dashboard && make dev-frontend
# Run an agent that overrides forward_in. Open its edge popup →
# the forward_in chip is "active" with a tooltip.
# Run an agent with stream=True. Open its run page → the chunk-replay
# panel is visible; pressing play replays the chunks.
```
