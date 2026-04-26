# Agent View Redesign — Master Implementation Plan

Single PR. No backwards compatibility. Demolish + rebuild. Branch: `agent-view-redesign`.

Reference: `SCAFFOLDING.md` for existing primitives, hooks, types, routes, backend endpoints.

---

## North star

Tabs at the top of the run-detail page (Overview / Graph / Invocations). Sidebar reads runs by class name with run_id underneath. Overview is one hero card + accordion sections that collapse empty states. Graph is full-bleed split-screen with an inline tabbed inspector replacing all popups and the side drawer. Every block is a json-render-registered component so backend (or AI) can compose layouts.

## Visual system targets (Phase 0 enforces these)

- **Type ladder**: hero 28/36 medium · h2 18/26 medium · h3 14/22 medium · body 14/22 · eyebrow 11 uppercase 0.08em muted · micro 11 mono.
- **Single accent**, three elevations (page bg-1 / card bg-2+shadow-card-soft / inspector bg-1+shadow-inspector). Hash colors only as 8px dot identity tokens.
- **Spacing scale** 4/8/12/16/24/32/48; cards radius 12, chips 8, pills full.
- **Motion** 80/150/200/220 ms via framer-motion.

---

## Phase 0 — Design foundation

**Tokens (extend `apps/frontend/src/styles/tokens.css`)**:
- New: `--shadow-card-soft`, `--shadow-inspector`, `--motion-quick`, `--motion-reveal`, `--motion-tab`.
- Larger base font-size (14px); spacing system handled via Tailwind classes.

**New atoms in `apps/frontend/src/components/ui/`**:
- `eyebrow.tsx`, `stat-tile.tsx`, `section.tsx` (accordion), `hash-tag.tsx`, `pill.tsx`, `icon-button.tsx`, `sparkline.tsx`, `field-tree.tsx`, `key-value-grid.tsx`, `divider.tsx`.
- Update `index.ts` and `registry.tsx` to export+register all atoms.

**Dependencies**:
- Add `framer-motion` to package.json.

---

## Phase 1 — Sidebar polish

**Files touched**:
- Rewrite `apps/frontend/src/components/panels/runs-sidebar/run-row.tsx` — two-line, no checkbox/star/badge, hash-tag dot.
- Refactor `apps/frontend/src/components/panels/runs-sidebar/run-list-sidebar.tsx` — header gets `[search 🔍] [filter ⚙︎] [collapse ←]` icons; popovers replace inline chips.
- New `apps/frontend/src/components/panels/runs-sidebar/sidebar-search-popover.tsx`.
- New `apps/frontend/src/components/panels/runs-sidebar/sidebar-filter-popover.tsx`.
- Selection: Cmd+click toggles; multiselect footer shows when ≥2.
- Delete `apps/frontend/src/hooks/use-pinned-runs.ts` and any references.
- Delete archive UI: `ArchivePage.tsx`, `ArchivedRunPage.tsx`, route + nav link.
- Update `apps/frontend/src/components/panels/runs-sidebar/run-row.test.tsx` to match new shape (or delete and rewrite).

---

## Phase 2 — Page shell with top tabs

**Routing** (`apps/frontend/src/dashboard/routes.tsx`):
- Replace `runs/:runId` with nested:
  ```
  { path: "runs/:runId", element: <RunDetailLayout />, children: [
    { index: true, element: <OverviewTab /> },
    { path: "graph", element: <GraphTab /> },
    { path: "invocations", element: <InvocationsTab /> },
  ]}
  ```

**New files**:
- `apps/frontend/src/dashboard/pages/RunDetailLayout.tsx` — shell with breadcrumb + AgentHero + tabs + Outlet.
- `apps/frontend/src/dashboard/pages/OverviewTab.tsx` — fetches and renders overview layout JSON via DashboardRenderer.
- `apps/frontend/src/dashboard/pages/GraphTab.tsx` — fetches/renders graph layout; auto-collapses sidebar via `useSidebarAutoCollapse`.
- `apps/frontend/src/dashboard/pages/InvocationsTab.tsx`.
- `apps/frontend/src/components/agent-view/page-shell/agent-tabs.tsx` — sticky tab bar (radix Tabs styled).
- `apps/frontend/src/components/agent-view/page-shell/agent-hero.tsx` — class name + state pill + stats line.
- `apps/frontend/src/components/agent-view/page-shell/use-sidebar-auto-collapse.ts` — collapses on route enter, restores on leave.

**Delete**:
- Old `RunDetailPage.tsx` becomes `RunDetailLayout.tsx`.

**Layouts** (in `apps/frontend/src/layouts/`):
- New `agent/overview.json`, `agent/graph.json`, `agent/invocations.json`.
- Delete `agents.json` (was the catch-all).
- Update `layouts/index.ts` resolution order: tab-specific lookup (agent overview vs graph vs invocations).

---

## Phase 3 — Overview tab

**Expression evaluator** in `apps/frontend/src/components/runtime/source-resolver.ts`:
- Extend `resolveSource` to support `$expr:funcName(arg)` with whitelist: `latest`, `count`, `hashes`, `reproSummary`, `driftSummary`, `costSummary`, `backendSummary`, `configSummary`, `examplesSummary`, `sisterRunsSummary`, `pluck`.

**New blocks** (each a json-render component with Zod schema):
- `apps/frontend/src/components/agent-view/overview/latest-invocation-card.tsx`
- `apps/frontend/src/components/agent-view/overview/invocations-list.tsx`
- `apps/frontend/src/components/agent-view/overview/io-field-preview.tsx`
- `apps/frontend/src/components/agent-view/overview/reproducibility-block.tsx`
- `apps/frontend/src/components/agent-view/overview/backend-block.tsx`
- `apps/frontend/src/components/agent-view/overview/config-block.tsx`
- `apps/frontend/src/components/agent-view/overview/examples-block.tsx`
- `apps/frontend/src/components/agent-view/overview/drift-block.tsx`
- `apps/frontend/src/components/agent-view/overview/cost-latency-block.tsx`
- `apps/frontend/src/components/agent-view/overview/sister-runs-block.tsx`
- `apps/frontend/src/components/agent-view/overview/registry.tsx`

**Compose** in `apps/frontend/src/layouts/agent/overview.json`:
- Hero is the page-level AgentHero (Phase 2), not a block here.
- Order: LatestInvocationCard → InvocationsList → AccordionGroup of {Reproducibility, Backend, Config, Examples, Drift, CostLatency, SisterRuns}.

**Delete**:
- `apps/frontend/src/components/agent-view/insights/agent-insights-row.tsx` and the chunky 6-card row entirely.
- `apps/frontend/src/components/agent-view/insights/registry.tsx` (insights vanish; replaced by overview/* blocks).
- `apps/frontend/src/components/agent-view/metadata/agent-metadata-panel.tsx` (data moves into AgentHero).
- `apps/frontend/src/components/agent-view/metadata/invocations-table.tsx` (replaced by InvocationsList).

---

## Phase 4 — Graph tab

**Routing**: `/runs/:runId/graph` enters; sidebar auto-collapses.

**Split layout**:
- `apps/frontend/src/components/agent-view/graph/split-pane.tsx` — resizable, default 50/50, persisted in `useUIStore.graphSplitWidth`.
- `apps/frontend/src/components/agent-view/graph/graph-page.tsx` — the SplitPane host.

**Selection state** (move from local to global):
- Extend `apps/frontend/src/stores/ui.ts`:
  - `graphSelection: { kind: "node"|"edge"|"group", id: string } | null`
  - `graphInspectorTab: "overview"|"invocations"|"prompts"|"events"|"experiment"|"langfuse"|"fields"`
  - `graphSplitWidth: number` (persisted)
  - Replace old `drawer/openDrawer/closeDrawer/drawerWidth/drawerKind` API entirely.
  - Keep `selectedInvocation*` and `comparisonInvocation*` (used by Phase 3 InvocationsList).

**Graph canvas rework** (`apps/frontend/src/components/agent-view/graph/`):
- Rewrite `interactive-graph.tsx` — selection lives in store; popups removed; toolbar shrinks to `[Fit] [Expand all] [Collapse all] [Copy Mermaid]`.
- New `composite-group-node.tsx` — React Flow group node with chevron header.
- New `agent-edge-card.tsx` — replaces edge label; 160×64 card with hash dot + class name + latency/tokens; corner glyphs.
- Rewrite `io-type-node.tsx` → `io-type-card.tsx` — dynamic-width card with field preview + `+N more` pill.
- Rewrite `layout.ts` — adaptive `rankdir` heuristic, tighter spacing, dynamic node width.
- New `use-active-agents.ts` — derives active agent paths from event buffer for live pulse.

**Inspector** (replaces drawer entirely):
- `apps/frontend/src/components/agent-view/graph/inspector/inspector-shell.tsx` — reads selection, renders nothing if null; tabbed shell otherwise.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-overview.tsx` — agent overview (role/task/rules/config/hooks/hashes).
- `apps/frontend/src/components/agent-view/graph/inspector/tab-invocations.tsx` — agent's invocations.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-prompts.tsx` — prompt diff strip + rendered prompt.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-events.tsx` — filtered event timeline.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-experiment.tsx` — prompt editor + invoke.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-langfuse.tsx` — embedded iframe.
- `apps/frontend/src/components/agent-view/graph/inspector/tab-fields.tsx` — type-node field tree.

**Delete**:
- `apps/frontend/src/components/agent-view/drawer/side-drawer.tsx`
- `apps/frontend/src/components/agent-view/drawer/drawer-host.tsx`
- `apps/frontend/src/components/agent-view/drawer/drawer-registry.ts`
- `apps/frontend/src/components/agent-view/drawer/views/*` (all of them — ports into inspector tabs)
- `apps/frontend/src/components/agent-view/drawer/registry.tsx`
- `apps/frontend/src/components/agent-view/graph/io-node-popup.tsx`
- `apps/frontend/src/components/agent-view/graph/agent-edge-popup.tsx`
- `apps/frontend/src/components/agent-view/graph/parameters-panel.tsx` (rebuilt as inspector content)
- `apps/frontend/src/components/agent-view/graph/config-section.tsx` (rebuilt)
- `apps/frontend/src/components/agent-view/graph/hook-badge.tsx` (rebuilt)
- `apps/frontend/src/components/agent-view/graph/field-row.tsx` (FieldTree replaces it)

**Shell update** (`apps/frontend/src/dashboard/Shell.tsx`):
- Remove `<SideDrawer />` import + render.

---

## Phase 5 — Invocations tab + inventory features

**Invocations tab** (`apps/frontend/src/dashboard/pages/InvocationsTab.tsx`):
- Full virtualized list (reuse `useVirtualizer`); reuse the new `InvocationsList` block.
- Filters per-agent (path picker), status, time range.

**Backend changes**:
- `apps/dashboard/operad_dashboard/agent_routes.py`:
  - New `GET /runs/by-hash?hash_content=X` → `{ matches: RunSummary[] }`.
- `apps/dashboard/operad_dashboard/layout_routes.py` (new):
  - `GET /runs/:id/layout/:tab` returns the bundled JSON layout for the requested tab. Plain agent runs get the default; algorithm runs can return enriched layouts.
- Wire into `app.py`.

**Frontend wiring**:
- `apps/frontend/src/lib/api/dashboard.ts`: add `runsByHash`, `runLayout` methods.
- `apps/frontend/src/lib/types.ts`: add response schemas.
- Hash color identity propagated via the new `HashTag` atom (sidebar, hero, edge cards, breadcrumb, fingerprint dots).
- Trainable params strip — `apps/frontend/src/components/agent-view/overview/trainable-params-block.tsx`. Renders only when meta has trainable.
- Live activity glyph — `agent-edge-card.tsx` reads `useActiveAgents`.
- Mermaid copy — toolbar action on graph page.
- Cassette indicator — invocation row glyph if `metadata.cassette` present.

---

## Phase 6 — Final demolition + verification

**Delete checklist** (already covered above; final pass to confirm clean tree):
- All of `apps/frontend/src/components/agent-view/drawer/**`
- `agent-edge-popup.tsx`, `io-node-popup.tsx`, `parameters-panel.tsx`, `config-section.tsx`, `hook-badge.tsx`, `field-row.tsx`
- `agent-insights-row.tsx`, all `insights/**` files (each card moves to overview/*)
- Old `agent-metadata-panel.tsx`, `invocations-table.tsx`, `script-origin-chip.tsx`, `hash-chip.tsx`
- `usePinnedRuns` hook + tests
- `ArchivePage.tsx`, `ArchivedRunPage.tsx`, archive routes, archive nav link
- Old `agents.json` layout
- Tests targeting deleted files

**Verification gates**:
- `pnpm -C apps/frontend typecheck`
- `pnpm -C apps/frontend test`
- `pnpm -C apps/frontend lint`
- `uv run pytest apps/dashboard/tests/ -q`
- Manual: `make clean && make build-frontend && make rebuild && make example-observed EXAMPLE=01_composition_research_analyst.py` → click into the run, exercise each tab.

---

## Sequencing while executing

1. Phase 0 (foundation) — 60 min. Atoms + tokens + framer-motion install.
2. Phase 1 (sidebar) — 45 min. Two-line row + popovers + delete archive + delete pin.
3. Phase 2 (shell) — 60 min. Nested routes + AgentHero + AgentTabs + tab pages.
4. Phase 3 (overview) — 120 min. 11 blocks + expression evaluator + overview.json.
5. Phase 4 (graph + inspector) — 150 min. SplitPane + 4 graph rebuilds + 7 inspector tabs + drawer deletion.
6. Phase 5 (invocations + features) — 75 min. InvocationsTab + sister-runs endpoint + hash identity propagation + live activity + mermaid copy.
7. Phase 6 (demolition + verify) — 60 min. Sweep deletions + typecheck + lint + tests.

Total: ~9 hours of focused work.

## When in doubt

- The existing `useUIStore` drawer keys are dead after Phase 4; I'm replacing them, not preserving them.
- `agents.json` is the *single* layout currently consumed; safe to replace with three tab-specific layouts.
- `pickLayout(algorithmPath)` is keyed off the algorithm path. The new flow is keyed off the tab name (overview/graph/invocations); algorithm-specific overrides come later via the backend hint.
- pnpm is the package manager.
