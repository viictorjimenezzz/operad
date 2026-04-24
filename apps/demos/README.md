# operad demos

Narrative, end-to-end showcases that import operad like any downstream
user. Different from `examples/`: those are mini-tutorials per
primitive; these are whole-story demos you can point a skeptic at.

## Available

- **[`agent_evolution/`](agent_evolution/README.md)** — a seed agent
  evolved over N generations via `Agent.auto_tune`. Offline-friendly,
  deterministic, optionally streams to the web dashboard.

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
