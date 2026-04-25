# `apps/` — sibling apps that consume operad

Each subfolder is an installable project that depends on `operad` like
any other downstream user. Apps do not modify `operad/` internals — if
a primitive belongs in operad, it lands there in a focused commit
first, then the app consumes it.

## Apps

- **`dashboard/`** — local-first web UI over the operad event bus
  (FastAPI + SSE + htmx + Mermaid.js). Per-run panels at
  `/runs/{run_id}` for fitness, mutation heatmap, prompt drift,
  training progress. Optional "View in Langfuse" deep-link.
  Default port: **7860**.
- **`studio/`** — human-feedback labeling + training launcher.
  Default port: **7870**.
- **`demos/`** — runnable showcases (currently `agent_evolution/`).

## Run individually

Each app is an independent uv-managed package. From the operad repo
root:

```bash
uv pip install -e apps/dashboard/         # then: operad-dashboard
uv pip install -e apps/studio/            # then: operad-studio
```

## Self-hosted observability stack (Langfuse + OTel)

A unified `docker-compose.yml` at the repo root spins up Langfuse v3
alongside both apps. operad's `OtelObserver` ships spans to Langfuse
via OTLP/HTTP; the dashboard renders a "View in Langfuse" deep-link
on every run-detail page (the OTel `trace_id` is derived from operad's
`run_id`, so the link resolves directly to
`{LANGFUSE_PUBLIC_URL}/trace/{run_id}` with no extra mapping).

```bash
cp .env.example .env
# Edit .env — set the LANGFUSE_INIT_PROJECT_*_KEY pair, the user
# password, and any rotation-worthy secrets. Then:
bash scripts/langfuse_otel_header.sh --update    # writes OTEL_EXPORTER_OTLP_HEADERS
docker compose up -d
```

Exposed ports: Langfuse on 3000, dashboard on 7860, studio on 7870.
See the repo-root README for the architecture and walkthrough.
