# `apps/frontend/`

Shared React 19 + TypeScript UI consumed by both `apps/dashboard/`
(port 7860) and `apps/studio/` (port 7870). Each app's FastAPI
backend mounts the corresponding built bundle from `dist-dashboard/`
or `dist-studio/`.

For the design rationale see
[`/Users/viictorjimenezzz/.claude/plans/system-instruction-you-are-working-floating-puppy.md`](../../../../.claude/plans/system-instruction-you-are-working-floating-puppy.md)
(or wherever the plan ended up under your home `.claude/plans/`).

## Stack

- React 19, TypeScript 5.6 (`strict`), Vite 5
- TanStack Query v5 (server state) + Zustand v5 (client state)
- React Router v7 (browser router)
- Tailwind v4 + shadcn/ui (PR2)
- `@json-render/{core,react}` (per-algorithm dashboard layouts)
- Zod 3 (layout schema, SSE envelope union, API responses)
- Recharts (charts), Mermaid 11 lazy-loaded (agent graph)
- Biome (lint + format)
- Vitest + React Testing Library + happy-dom (unit)
- Playwright (E2E, three golden flows)

## Dev

```bash
pnpm install
pnpm dev:dashboard           # vite on :5173 → proxies to localhost:7860
pnpm dev:studio              # vite on :5174 → proxies to localhost:7870

# in another terminal
make dashboard               # operad-dashboard on :7860
make studio                  # operad-studio    on :7870
```

## Build

```bash
pnpm build                   # writes dist-dashboard/ and dist-studio/
pnpm build:dashboard
pnpm build:studio
```

`make build-frontend` (lands in PR6) rsyncs each dist into the matching
backend's `operad_<app>/web/` directory.

## Layout

```
src/
  main.dashboard.tsx          entry: Providers + DashboardApp
  main.studio.tsx             entry: Providers + StudioApp
  app/                        Providers, ErrorBoundary, mode context
  lib/                        api clients, sse dispatcher, layout schema, types  (PR2)
  stores/                     Zustand slices                                     (PR2)
  hooks/                      TanStack Query hooks                                (PR2)
  registry/                   json-render catalog + registry + resolver          (PR3)
  components/DashboardRenderer.tsx                                                (PR3)
  layouts/                    per-algorithm layout JSONs                          (PR4)
  shared/{ui,charts,panels}/  primitives + recharts + composite panels       (PR2-4)
  dashboard/                  routes + pages                                    (PR3)
  studio/                     routes + pages + studio-specific components       (PR5)
  styles/tokens.css           Tailwind v4 + dark theme tokens
```

## Tests

```bash
pnpm test                    # vitest, single run
pnpm test:watch
pnpm test:e2e                # playwright (gated behind OPERAD_E2E=1 in verify.sh)
pnpm typecheck               # tsc --noEmit
pnpm lint                    # biome check
```
