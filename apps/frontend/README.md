# `apps/frontend/`

Shared React 19 + TypeScript UI consumed by both `apps/dashboard/`
(port 7860) and `apps/studio/` (port 7870). Each app's FastAPI
backend mounts the corresponding built bundle from
`apps/<app>/operad_<app>/web/`.

## Stack

- React 19, TypeScript 5.9 (`strict`, `exactOptionalPropertyTypes`),
  Vite 5 multi-entry build
- TanStack Query v5 (server state) + Zustand v5 (client state)
- React Router v7 (browser router)
- Tailwind v4 (CSS-variable theme) + shadcn-style primitives
- `@json-render/{core,react}` (per-algorithm dashboard layouts)
- Zod 3 (layout schema, SSE envelope union, API responses)
- Recharts (every chart), Mermaid 11 lazy-loaded (agent graph)
- Biome (lint + format) — single-binary toolchain
- Vitest + React Testing Library + happy-dom (unit)
- Playwright (E2E, gated behind `OPERAD_E2E=1`)

## Dev

```bash
pnpm install
pnpm dev:dashboard           # vite on :5173 → proxies to localhost:7860
pnpm dev:studio              # vite on :5174 → proxies to localhost:7870

# in another terminal
make dashboard               # operad-dashboard on :7860
make studio                  # operad-studio    on :7870
```

Open http://localhost:5173/index.dashboard.html (dashboard) or
http://localhost:5174/index.studio.html (studio).

## Build

```bash
pnpm build                   # writes dist-dashboard/ and dist-studio/
pnpm build:dashboard
pnpm build:studio
```

The repo-root `make build-frontend` runs `pnpm build` and then rsyncs
each dist into the matching backend's `operad_<app>/web/` directory.
The hatchling wheel manifest in `apps/<app>/pyproject.toml`
force-includes `web/`, so the SPA ships inside the published package.

## Layout

```
src/
  main.dashboard.tsx          entry: Providers + DashboardApp + Router
  main.studio.tsx             entry: Providers + StudioApp + Router
  app/                        Providers, ErrorBoundary, mode context
  lib/                        api clients, sse dispatcher, layout schema, types
  stores/                     Zustand slices (ui, run, eventBuffer, stats, stream)
  hooks/                      TanStack Query hooks + SSE hooks
  registry/                   json-render catalog + registry + source resolver
  components/DashboardRenderer.tsx     wrapper around <Renderer> from @json-render
  layouts/                    per-algorithm layout JSONs (default + Evo + Trainer + Debate + Beam)
  shared/
    ui/                       primitives (Card, Tabs, Button, Badge, Chip, KPI, …)
    charts/                   FitnessCurve, PopulationScatter, MutationHeatmap,
                              TrainingProgress, TrainingLossCurve, DriftTimeline,
                              DebateRoundView, BeamCandidateChart, AgentGraph
    panels/                   RunListSidebar, EventTimeline,
                              IODetail, RawEnvelopePanel, MetaListPanel, KpiTile,
                              LangfuseLink
  dashboard/                  Shell + routes + pages (RunList, RunDetail, NotFound)
  studio/                     Shell + routes + pages + studio-specific components
                              (JobList, JobRowCard, RatingForm, TrainingLauncher,
                               TrainingStatusStream)
  tests/fixtures/             real captures from agent_evolution: JsonlObserver
                              trace + /runs/{id}/events response
  styles/tokens.css           Tailwind v4 @theme + dark palette tokens
```

## Adding a per-algorithm dashboard

See [`src/layouts/README.md`](src/layouts/README.md). Short version:
drop a JSON, register it in `src/layouts/index.ts`, write a Vitest
spec, and (if a new component is needed) add it to both
`src/registry/catalog.ts` and `src/registry/registry.tsx`.

## Tests

```bash
pnpm test                    # vitest, single run (incl. real-fixture parse tests)
pnpm test:watch
pnpm test:e2e                # playwright
pnpm typecheck               # tsc --noEmit
pnpm lint                    # biome check
```
