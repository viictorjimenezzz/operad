# operad-studio

Local-first human-feedback labeling + training launcher for operad.

Studio reads NDJSON jobs produced by `operad.train.HumanFeedbackCallback`,
lets a single human assign 1-5 ratings plus a rationale to each row,
and then launches `Trainer.fit` with `HumanFeedbackLoss` against the
rated file. Training events forward to the running dashboard via
`operad.dashboard.attach` so the full observability stack (fitness
curve, mutation heatmap, drift timeline, progress widget) stays in
sync.

## Install

```
uv pip install -e apps/studio/
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
