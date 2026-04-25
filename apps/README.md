# `apps/` — sibling apps that consume operad

Each subfolder is an installable project that depends on `operad` like
any other downstream user. Apps do not modify `operad/` internals — if
a primitive belongs in operad, it lands there in a focused commit
first, then the app consumes it.

## Apps

- **[`dashboard/`](dashboard/)** — local-first web UI over the operad
  event bus. FastAPI + SSE backend; React 19 SPA (rendered from
  `apps/frontend/`) with per-algorithm layouts (EvoGradient / Trainer /
  Debate / Beam / default). Optional "View in Langfuse" deep-link.
  Default port: **7860**.
- **[`studio/`](studio/)** — human-feedback labeling + training
  launcher. Same React 19 SPA (different entry). Default port:
  **7870**.
- **[`frontend/`](frontend/)** — shared React 19 + TypeScript
  package consumed by both `dashboard/` and `studio/`. pnpm + Vite +
  Tailwind v4 + shadcn/ui + TanStack Query + Zustand +
  `@json-render/{core,react}`. Per-algorithm dashboards are JSON
  layouts under `src/layouts/` resolved at runtime via a
  `<DashboardRenderer>` wrapper around `@json-render/react`'s
  `<Renderer>`.
- **[`demos/`](demos/)** — runnable showcases (currently
  `agent_evolution/`).

## Run individually

Each app is an independent uv-managed package. From the operad repo
root:

```bash
uv pip install -e apps/dashboard/    # then: operad-dashboard
uv pip install -e apps/studio/       # then: operad-studio
make build-frontend                  # builds the SPA into both apps' web/ dirs
```

For local frontend dev with HMR (no docker needed):

```bash
# terminal A
make dashboard                       # FastAPI backend on :7860

# terminal B
make dev-frontend                    # vite dev server on :5173, proxies API to :7860
```

Then open http://localhost:5173/index.dashboard.html. Studio is the
same shape: `make studio` + `make dev-studio-frontend`, port 5174.

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

The `apps/dashboard/Dockerfile` and `apps/studio/Dockerfile` use a
multi-stage build: a Node stage builds the React bundle, then the
Python stage copies the bundle into `operad_<app>/web/` before
installing. The hatchling wheel manifest force-includes `web/` so
the SPA ships inside the package.

Exposed ports: Langfuse on 3000, dashboard on 7860, studio on 7870.
See the repo-root README for the architecture and walkthrough.
