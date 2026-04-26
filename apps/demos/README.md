# operad demos

Narrative, end-to-end showcases that import operad like any downstream
user. Different from `examples/`: those are mini-tutorials per
primitive; these are whole-story demos you can point a skeptic at.

## Available

- **[`agent_evolution/`](agent_evolution/README.md)** — a seed agent
  evolved over N generations via `Agent.auto_tune`. Offline-friendly,
  deterministic, optionally streams to the web dashboard.
- **[`triage_reply/`](triage_reply/README.md)** — compositional support
  triage tree evolved over generations. Offline-friendly, deterministic,
  streams to the web dashboard with graph + mutation panels.

## Planned

- `research_arena` — `AutoResearcher` + `FakeRetriever` over a
  hardcoded corpus, with the dashboard showing plan → retrieve →
  reason → verify → reflect.

## Conventions

- Demos live in `apps/demos/` (not in `operad/`). They use operad via
  `from operad import ...`.
- `--offline` is always the default path. A demo that needs a model
  server must say so in its README.
- Each demo has its own `README.md`, `run.py` CLI, and whatever
  helpers it needs. No shared framework.

## Observability

All demo CLIs support `--dashboard [HOST:PORT]` and `--no-open`.

```bash
# terminal A
uv run operad-dashboard --port 7860

# terminal B
uv run python apps/demos/agent_evolution/run.py --offline --dashboard
uv run python apps/demos/triage_reply/run.py --dashboard
```

To also export spans to self-hosted Langfuse:

```bash
OPERAD_OTEL=1 \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:3000/api/public/otel \
uv run --extra otel python apps/demos/triage_reply/run.py --dashboard
```
