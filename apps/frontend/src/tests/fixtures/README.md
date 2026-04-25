# SSE / envelope fixtures

Real-event captures used by Vitest specs to verify our Zod schemas
against the wire shapes operad actually produces.

| File                                | Source                               | Format |
| ----------------------------------- | ------------------------------------ | ------ |
| `agent-evolution-trace.jsonl`       | `OPERAD_TRACE=…` JsonlObserver       | One JSON object per line; discriminator field is `event` (`"agent"` or `"algorithm"`) |
| `agent-evolution-events.json`       | `GET /runs/{run_id}/events?limit=…`  | `{ run_id, events: Envelope[] }`; events use the SSE `type` discriminator |

## Re-capturing

```bash
# Boot the dashboard (in another terminal):
make dashboard

# Run a demo with both local trace + dashboard attach:
OPERAD_TRACE=/tmp/operad-events.jsonl \
  uv run python apps/demos/agent_evolution/run.py \
    --offline --no-open --dashboard 127.0.0.1:7860 \
    --generations 4 --population 6 --seed 0

# Snapshot the SSE-format events the dashboard buffered:
RUN_ID=$(curl -s http://127.0.0.1:7860/runs | jq -r '.[0].run_id')
curl -s "http://127.0.0.1:7860/runs/$RUN_ID/events?limit=500" \
  > apps/frontend/src/tests/fixtures/agent-evolution-events.json
cp /tmp/operad-events.jsonl \
  apps/frontend/src/tests/fixtures/agent-evolution-trace.jsonl
```

The Vitest spec (`src/tests/fixtures.test.ts`) parses every record
through the `Envelope` schema. JsonlObserver records are converted
first via `jsonlRecordToEnvelope()` (mirrors
`apps/dashboard/operad_dashboard/replay.py:record_to_envelope`).
