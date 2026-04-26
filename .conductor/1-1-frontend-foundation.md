# 1-1 Frontend foundation: per-folder registry convention

## Scope

You are doing a wholesale rebuild of the frontend component
architecture in `apps/frontend/`. **Demolish, then rebuild** — no
backcompat. The goal is to land the new per-folder registry
convention everywhere, leaving the codebase in a state where the
agent-view streams (iter 2+) can drop new components into
`agent-view/<sub>/` and have them work with zero scaffolding.

### You own

- `apps/frontend/src/components/` — entire new tree.
- `apps/frontend/src/stores/ui.ts` — extend with sidebar collapse +
  drawer state machine (see "Contracts" below).
- `apps/frontend/src/dashboard/Shell.tsx` and routes — rewire to the
  new components.
- All consumers of the old paths (`@/shared/...`, `@/registry/...`,
  `@/components/DashboardRenderer`) — update imports.
- Test files under `apps/frontend/src/**/*.test.{ts,tsx}` — update
  paths and selectors.
- `apps/frontend/vite.config.*` — update path aliases if you change
  them.

### Demolish

- `apps/frontend/src/registry/` (entire folder).
- `apps/frontend/src/shared/` (entire folder — UI primitives, panels,
  charts).
- `apps/frontend/src/components/DashboardRenderer.tsx` (replaced).
- `apps/frontend/src/layouts/default.json` (replaced by `agents.json`
  in stream 2-1; for now leave a sensible "no layout" fallback in
  the resolver — a clear empty state, not a thrown error).

### Out of scope

- The contents of `agent-view/` sub-folders (iter 2 fills them).
  Just create empty stubs so the tree exists.
- Backend changes (1-3 owns).
- Operad core (1-2 owns).
- Algorithm-layout JSON (`evogradient.json`, `beam.json`, etc.) —
  those keep working as long as their referenced component names
  resolve in the new registry.

---

## Vision

Today the frontend has one monolithic `src/registry/registry.tsx`
that hardcodes 40+ entries, with components scattered across
`src/shared/{ui,panels,charts}/`. Adding a new component requires
edits in three places (component file, catalog, registry) and any
two streams touching components will conflict.

Mirror the upstream `vercel-labs/json-render` shape: each component
domain owns its Zod definitions and its React implementations,
bundled at the folder level, then composed by spread at the top.
This makes the registry extensible by *adding files*, not editing
shared ones.

The new tree:

```
apps/frontend/src/components/
├── runtime/
│   ├── dashboard-renderer.tsx     # the SSE+TanStack Query orchestrator
│   ├── source-resolver.ts         # $context/$queries/$run.events resolution
│   ├── sse-dispatcher.ts          # moved from src/lib
│   └── index.ts
├── ui/                            # primitives: Card, Button, Tabs, Badge, ChipRow, JSONView, EmptyState, Toolbar, ...
│   ├── card.tsx
│   ├── tabs.tsx
│   ├── ...
│   ├── registry.tsx
│   └── index.ts
├── panels/                        # composites that aren't algorithm-specific
│   ├── kpi/
│   ├── meta-list/
│   ├── event-timeline/
│   ├── io-detail/
│   ├── raw-envelope/
│   ├── runs-sidebar/              # the run list + collapse rail (see "Sidebar" below)
│   ├── langfuse-link/
│   ├── langfuse-summary-card/
│   ├── global-stats-bar/
│   ├── registry.tsx               # spreads all sub-folder registries
│   └── index.ts
├── charts/                        # algorithm-agnostic graph visualisations
│   ├── mermaid-graph/             # static fallback for archive snapshots
│   ├── registry.tsx
│   └── index.ts
├── algorithms/
│   ├── evogradient/               # FitnessCurve, PopulationScatter, MutationHeatmap, OpSuccessTable, GradientLog
│   │   ├── ...
│   │   ├── registry.tsx
│   │   └── index.ts
│   ├── trainer/                   # TrainingProgress, TrainingLossCurve, LrScheduleCurve, CheckpointTimeline, DriftTimeline
│   ├── beam/                      # BeamCandidateChart, ConvergenceCurve, IterationProgression
│   ├── debate/                    # DebateRoundView, DebateTranscript, DebateConsensusTracker
│   ├── sweep/                     # SweepHeatmap, SweepBestCellCard, SweepCostTotalizer
│   ├── registry.tsx               # spreads all algorithm bundles
│   └── index.ts
├── agent-view/                    # NEW — empty stubs only in this stream
│   ├── metadata/                  # 2-1 fills
│   ├── graph/                     # 2-2 fills
│   ├── drawer/                    # 2-3 fills
│   ├── insights/                  # 2-4 fills
│   ├── registry.tsx               # spreads sub-registries; OK to start empty
│   └── index.ts
├── registry.tsx                   # composes the entire app registry
└── index.ts
```

Pick the file shapes inside each folder yourself based on what's
clean. The flat-file vs. one-folder-per-component split is a
judgment call. Match the upstream `vercel-labs/json-render` shadcn
example as a north star.

---

## Sidebar collapse (sub-deliverable)

The current `RunListSidebar` is non-collapsible. Rebuild it under
`panels/runs-sidebar/` with:

- A chevron button at the top that toggles between **expanded** (full
  width with run rows) and **rail** (~48px with just algorithm
  group icons / first-letter avatars and the global toolbar
  collapsed to icon buttons).
- Persist the collapsed flag to localStorage and to
  `useUIStore.sidebarCollapsed`.
- Rail mode keeps run selection working (clicking an avatar opens a
  popover showing the runs in that group).
- Smooth CSS transition, focus management, keyboard shortcut
  (`cmd+\`).

Don't lose any current functionality — search, filters, pinning,
follow-toggle all stay.

---

## Contracts you expose for sibling streams

### `useUIStore` extensions (pinned API)

```ts
// apps/frontend/src/stores/ui.ts (extend, don't fork)
type DrawerKind = "langfuse" | "events" | "prompts" | "values" | null;
type DrawerPayload = { agentPath?: string; attr?: string; side?: "in" | "out"; [k: string]: unknown };

interface UIStoreShape {
  sidebarCollapsed: boolean;
  toggleSidebar(): void;
  setSidebarCollapsed(v: boolean): void;

  drawer: { kind: DrawerKind; payload: DrawerPayload } | null;
  drawerWidth: number;            // px, persisted to localStorage
  openDrawer(kind: Exclude<DrawerKind, null>, payload?: DrawerPayload): void;
  closeDrawer(): void;
  setDrawerWidth(px: number): void;
}
```

The shell layout reserves space for the drawer when open and
animates it in. The drawer *content* component is owned by stream
2-3; you only define the state and the layout reservation.

### Agent-view sub-folder stubs

Create the sub-folders (`metadata/`, `graph/`, `drawer/`,
`insights/`) with stub `registry.tsx` files that export empty
`*Definitions` and `*Components` objects. The top-level
`agent-view/registry.tsx` spreads them. This gives iter-2 streams
a clean drop-in point.

### Top-level registry

The composed registry is the single export point used by
`runtime/dashboard-renderer.tsx`. Naming and re-exports are your
call as long as it follows the json-render `defineRegistry` API.

---

## Implementation pointers

- The current SSE dispatcher (`src/lib/sse-dispatcher.ts`), source
  resolver (`src/lib/resolveProps`), and the dashboard renderer's
  TanStack-Query+SSE merge logic are well-structured — port them
  into `components/runtime/` as-is, just rename and re-export.
- Component renderers should follow the existing pattern of casting
  `element.props as Shape`. Don't re-validate props at the renderer
  layer; that's the catalog's job.
- Use a workspace-wide find-and-replace for import paths, then
  `pnpm typecheck` to surface stragglers.
- `vite.config` may need `@/components` alias added (or the
  existing `@/` may already cover it).
- Algorithm chart files (40+) are mostly mechanical moves. Don't
  rewrite their internals; just relocate, update imports, and
  register them in the new per-algorithm `registry.tsx`.

---

## Be creative

- The catalog Zod definitions are an opportunity to tighten prop
  types beyond what the current `catalog.ts` does. Look for `data?: unknown`
  passthroughs and replace with stronger types where the source
  shape is known.
- The runtime renderer is where streaming, error boundaries, and
  loading states live. There's headroom to do this more elegantly
  than today (e.g. per-element error boundaries with dev-mode
  prop-shape diagnostics).
- Sidebar rail mode is a chance to think about how the dashboard
  feels at a glance. A sparkline of recent activity per group? A
  pulse animation when a new event arrives? Use your judgment.
- Look at how shadcn-ui's blocks are organised and at the
  `@json-render/shadcn` package for inspiration on the
  catalog/components split.

---

## Verification

```bash
pnpm -C apps/frontend install
pnpm -C apps/frontend typecheck      # MUST be green
pnpm -C apps/frontend test
pnpm -C apps/frontend lint
make dashboard                       # smoke: server boots
make dev-frontend                    # smoke: SPA loads, sidebar toggles
```

The dashboard should still render the existing per-algorithm runs
(open an evogradient run from a recorded fixture or run
`apps/demos/agent_evolution/`). If algorithm layouts break because
their referenced component names disappeared, the migration is
incomplete — fix it before opening the PR.
