# operad-studio

Local-first human-feedback labeling + training launcher for operad.

Studio reads NDJSON jobs produced by `operad.train.HumanFeedbackCallback`,
lets a single human assign 1-5 ratings plus a rationale to each row,
and then launches `Trainer.fit` with `HumanFeedbackLoss` against the
rated file. Training events forward to the running dashboard via
`operad.dashboard.attach` so the full observability stack (fitness
curve, mutation heatmap, drift timeline, progress widget) stays in
sync.

The frontend is the React 19 SPA in [`apps/frontend/`](../frontend/),
shared with `operad-dashboard`. The Python side is FastAPI; the SPA
bundle is built once and served from `operad_studio/web/`.

## Install

```
uv pip install -e apps/studio/
make build-frontend          # one-shot SPA build into operad_studio/web
```

## Run

```
operad-studio --port 7870 \
              --data-dir /tmp/operad-feedback \
              --agent-bundle /tmp/talker.json \
              [--dashboard-port 7860]
```

- `--data-dir` — directory of `*.jsonl` jobs (each one a
  `HumanFeedbackCallback` dump).
- `--agent-bundle` — `Trainer.save()` bundle used as the starting
  point for training runs.
- `--dashboard-port` — if set, training events also stream to the
  dashboard at that port.

Trained bundles are written back to the data directory as
`<job>-trained.json` so the next round can label further outputs.

### Frontend dev loop

```bash
# terminal A: backend
make studio

# terminal B: vite dev server with HMR (proxies /jobs to :7870)
make dev-studio-frontend
```

Open http://localhost:5174/index.studio.html.

## API surface

JSON endpoints consumed by the SPA (and stable for any external tool):

- `GET /jobs` — `[{name, total_rows, rated_rows, unrated}]`
- `GET /jobs/{name}/rows` — `{rows: JobRow[], total, rated}`
- `POST /jobs/{name}/rows/{row_id}` — form-encoded `rating` + `rationale`
- `POST /jobs/{name}/train` — form-encoded `epochs` + `lr` (returns 202)
- `GET /jobs/{name}/train/stream` — SSE event log for a running training
- `GET /jobs/{name}/download` — full NDJSON of the rated job
- `GET /api/manifest` — `{mode, version, dataDir, dashboardPort}`

`JobRow` shape mirrors `operad.train.HumanFeedbackCallback`:
`{id, run_id, agent_path, input, expected, predicted, rating, rationale, written_at}`.
