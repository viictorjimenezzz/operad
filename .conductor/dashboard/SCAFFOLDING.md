# Operad Frontend & Backend Scaffolding Reference

## 1. UI Components (`apps/frontend/src/components/ui/`)

### Card
**File:** `card.tsx`  
**Exports:** `Card`, `CardHeader`, `CardTitle`, `CardContent`  
**Props:** `React.HTMLAttributes<HTMLDivElement>` (all forwardRef with `className` + standard div attrs)  
**Usage:** Compose as `<Card><CardHeader><CardTitle>Title</CardTitle></CardHeader><CardContent>Content</CardContent></Card>`. Styled with border, bg-1 background, inset shadow.

### Button
**File:** `button.tsx`  
**Props:** `ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>`  
**Variants:** `{ variant: "default" | "primary" | "ghost" | "danger"; size: "sm" | "md" | "lg" | "icon" }`  
**Usage:** `<Button variant="primary" size="md">Click me</Button>`. Default `type="button"`. Renders with CVA-driven Tailwind classes.

### Badge
**File:** `badge.tsx`  
**Props:** `BadgeProps = HTMLAttributes<HTMLSpanElement> & { variant?: "default" | "live" | "ended" | "error" | "algo" | "warn" }`  
**Usage:** `<Badge variant="live">RUNNING</Badge>`. Compact inline badge with semantic color variants.

### Chip
**File:** `chip.tsx`  
**Props:** `ChipProps = ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }`  
**Usage:** `<Chip active={isSelected} onClick={...}>Filter</Chip>`. Pill-shaped, toggleable appearance.

### EmptyState
**File:** `empty-state.tsx`  
**Props:** `{ title: string; description?: ReactNode; cta?: ReactNode; className?: string }`  
**Usage:** `<EmptyState title="No data" description="Try again later" cta={<Button>Refresh</Button>} />`. Centered layout for empty containers.

### SearchInput
**File:** `search-input.tsx`  
**Props:** `{ value: string; onChange: (v: string) => void; placeholder?: string }`  
**Usage:** `<SearchInput value={q} onChange={setQ} />`. Controlled input with icon; reads `value` and calls `onChange` on every keystroke.

### Additional Components
- **KPI** (`kpi.tsx`): `{ label: string; value: ReactNode; sub?: ReactNode; className?: string }` – metric display card.
- **MetaList** (`meta-list.tsx`): `{ items: Array<{ label: string; value: ReactNode }>; className?: string }` – definition-list layout.
- **JsonView** (`json-view.tsx`): `{ value: unknown; className?: string; collapsed?: boolean }` – syntax-highlighted JSON preview.
- **Tabs** (from radix-ui): `TabsList`, `TabsTrigger`, `TabsContent` – radix-ui v1.1.0 tab group.

---

## 2. JSON-Render Integration

### Registry (`apps/frontend/src/components/ui/registry.tsx`)
`defineRegistry` shape (from `@json-render/react`):
```typescript
export const uiRegistry: ComponentRegistry = {
  Card: ({ element, children }) => <Card>{children}</Card>,
  Row: ({ element, children }) => <div className="flex flex-wrap gap-3">{children}</div>,
  Col: ({ element, children }) => <div className="flex flex-col">{children}</div>,
  Tabs: ({ element, children }) => /* tabs with dynamic tabs array from element.props */,
  EmptyState: ({ element }) => <EmptyState {...element.props} />,
};
```
**Pattern:** Each registry entry is a component that receives `{ element, children }`. Props come from `element.props`; Zod schemas pair via `@json-render/react` tree rendering.

### DashboardRenderer (`apps/frontend/src/components/runtime/dashboard-renderer.tsx`)
**Props:**
```typescript
interface DashboardRendererProps {
  layout: LayoutSpec;
  context: Record<string, string>;  // e.g., { runId: "abc-123" }
}
```
**Behavior:**
- Reads `layout.dataSources` map and opens a TanStack Query per data source.
- Fetches each source's endpoint (with `context` path substitution).
- Subscribes to optional `.sse` streams for real-time updates.
- Resolves `$queries.X[.path]`, `$context.key`, `$run.events`, `$run.summary` placeholders.
- Does NOT support nested expressions or function calls; only path traversal.
- On SSE reconnect, invalidates query and re-backfills to catch up.

### Source Resolution (`source-resolver.ts`)
```typescript
resolveSource(expr: unknown, ctx: ResolveContext): unknown
// expr: "$queries.summary.generations[0].best" → returns value or undefined
// ctx: { context, queries, runEvents }

resolveProps(props: Record<string, unknown>, ctx: ResolveContext): Record<string, unknown>
// Converts props keys: sourceX → dataX (e.g., sourceFitness → dataFitness)
```

---

## 3. Routing Setup

**File:** `apps/frontend/src/dashboard/routes.tsx`  
**Pattern:** React Router v7.0.0 with `createBrowserRouter` and nested routes.

```typescript
export const dashboardRoutes = [
  {
    path: "/",
    element: <Shell />,  // layout wrapper
    children: [
      { index: true, element: <RunListPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
      { path: "archive", element: <ArchivePage /> },
      { path: "benchmarks", element: <BenchmarksPage /> },
      // ... more routes
    ],
  },
];

export const dashboardRouter = createBrowserRouter(dashboardRoutes);
```

**To add nested routes** (e.g., `/runs/:runId/graph`):
```typescript
{
  path: "runs/:runId",
  element: <RunDetailLayout />,
  children: [
    { index: true, element: <RunOverview /> },
    { path: "graph", element: <RunGraphPage /> },
    { path: "invocations", element: <RunInvocationsPage /> },
  ],
}
```

Use `<Outlet />` in the parent layout and `useParams()` to read `:runId` in children.

---

## 4. State Management (Zustand Stores)

### useUIStore (`apps/frontend/src/stores/ui.ts`)
**State:**
- `currentTab: string` – active tab/panel
- `eventKindFilter: "all" | "agent" | "algo" | "error"` – event filter
- `eventSearch: string` – event text search
- `autoFollow: boolean` – auto-scroll to latest event
- `eventsFollow: boolean` – follow/pin toggle
- `sidebarCollapsed: boolean`
- `drawer: { kind: DrawerKind; payload: DrawerPayload } | null` – active side drawer
  - `DrawerKind: "langfuse" | "events" | "prompts" | "values" | "find-runs" | "experiment" | "diff" | "gradients" | null`
  - `DrawerPayload: { agentPath?, attr?, side?, invocationId?, ... }` – drawer context
- `drawerWidth: number` – persisted in localStorage

**Actions:** `setCurrentTab`, `setEventKindFilter`, `setEventSearch`, `setAutoFollow`, `setEventsFollow`, `toggleSidebar`, `setSidebarCollapsed`, `openDrawer(kind, payload?)`, `closeDrawer`, `setDrawerWidth`, `setSelectedInvocation(id, path)`, `clearSelectedInvocation`, etc.

**Persistence:** partialize to localStorage under key `"operad.ui"`.

### useRunStore (`apps/frontend/src/stores/run.ts`)
**State:** `{ currentRunId, selectedEventIdx, setCurrentRun(id), setSelectedEventIdx(idx) }`

### useEventBufferStore (`apps/frontend/src/stores/eventBuffer.ts`)
**State:**
- `eventsByRun: Map<runId, EventEnvelope[]>` – rolling buffer (max 500 per run)
- `liveGenerations: Generation[]` – cross-run generations (max 200)
- `latestEnvelope: Envelope | null` – last received envelope

**Actions:** `ingest(envelope)` (auto-caps per limits), `clear(runId?)` (clear one or all)

### useRunsFilterStore (`apps/frontend/src/stores/runs-filter.ts`)
**State:** `{ search, statusFilter: "all" | "running" | "ended" | "errors", timeFilter: "all" | "1h" | "24h" | "7d", showSynthetic }`  
**Persisted to sessionStorage** under `"operad.runs-filter"`.

---

## 5. Hooks (`apps/frontend/src/hooks/`)

### useRuns / useRunsFiltered
```typescript
useRunsFiltered(includeSynthetic: boolean)
// queryKey: ["runs", { includeSynthetic }]
// refetchInterval: 5000ms
```

### useRunSummary
```typescript
useRunSummary(runId: string | null)
// queryKey: ["run", "summary", runId]
// enabled: !!runId
// Returns: RunSummary (Zod-validated)
```

### useRunEvents
```typescript
useRunEvents(runId: string, limit = 500)
// queryKey: ["run", "events", runId, limit]
// Returns: RunEventsResponse { run_id, events[] }
```

### useRunInvocations
```typescript
useRunInvocations(runId: string)
// queryKey: ["run", "invocations", runId]
// Returns: RunInvocationsResponse { agent_path?, invocations[] }
```

### useAgentMeta
```typescript
useAgentMeta(runId: string, agentPath: string)
// queryKey: ["run", "agent-meta", runId, agentPath]
// Returns: AgentMetaResponse (class_name, kind, config, schemas, etc.)
```

### useAgentValues, useAgentEvents
```typescript
useAgentValues(runId, agentPath, attr, side: "in" | "out")
// queryKey: ["run", "agent-values", runId, agentPath, attr, side]

useAgentEvents(runId, agentPath, limit = 500)
// queryKey: ["run", "agent-events", runId, agentPath, limit]
```

### useGraph, useFitness, useMutations, useDrift, useProgress
All follow same pattern: `queryKey: ["run", "name", runId]`, enabled on runId presence.

### usePinnedRuns
```typescript
usePinnedRuns() // returns store instance
usePinnedRunSummaries() // returns RunSummary[] for pinned IDs, auto-unpins stale
useIsPinned(runId) // boolean check
```

### useEvolution, useStats, useBenchmarks
Global queries for dashboard overview.

### useEventStream, usePanelStream
SSE subscription hooks. `useDashboardStream()` opens `/stream` and dispatches envelopes via `dispatchEnvelope()`.

---

## 6. API Client (`apps/frontend/src/lib/api/dashboard.ts`)

**Base:** `dashboardApi` object with typed methods. Each uses Zod schema validation.

**Core Routes:**
```typescript
dashboardApi.runs()                          // GET /runs → RunSummary[]
dashboardApi.runSummary(runId)              // GET /runs/{id}/summary → RunSummary
dashboardApi.runInvocations(runId)          // GET /runs/{id}/invocations → RunInvocationsResponse
dashboardApi.runEvents(runId, limit)        // GET /runs/{id}/events?limit=N → { run_id, events[] }
dashboardApi.agentMeta(runId, agentPath)    // GET /runs/{id}/agent/{path}/meta → AgentMetaResponse
dashboardApi.agentInvocations(runId, path)  // GET /runs/{id}/agent/{path}/invocations → AgentInvocationsResponse
dashboardApi.agentParameters(runId, path)   // GET /runs/{id}/agent/{path}/parameters → AgentParametersResponse
dashboardApi.agentValues(runId, path, attr, side)  // GET /runs/{id}/agent/{path}/values?attr=X&side=in|out
dashboardApi.agentPrompts(runId, path)      // GET /runs/{id}/agent/{path}/prompts → AgentPromptsResponse
dashboardApi.agentEvents(runId, path, limit) // GET /runs/{id}/agent/{path}/events?limit=N
dashboardApi.agentDiff(runId, path, fromId, toId) // GET /runs/{id}/agent/{path}/diff?from=X&to=Y
dashboardApi.graph(runId)                   // GET /graph/{id} → GraphResponse { mermaid }
dashboardApi.fitness(runId)                 // GET /runs/{id}/fitness.json → FitnessEntry[]
dashboardApi.mutations(runId)               // GET /runs/{id}/mutations.json → MutationsMatrix
dashboardApi.drift(runId)                   // GET /runs/{id}/drift.json → DriftEntry[]
dashboardApi.progress(runId)                // GET /runs/{id}/progress.json → ProgressSnapshot
dashboardApi.benchmarks()                   // GET /benchmarks → BenchmarkListItem[]
dashboardApi.benchmarkDetail(id)            // GET /benchmarks/{id} → BenchmarkDetailResponse
dashboardApi.manifest()                     // GET /api/manifest → Manifest { mode, version, langfuseUrl, allowExperiment }
dashboardApi.archive(params)                // GET /archive?from=N&to=N&algorithm=X → RunSummary[]
dashboardApi.archivedRun(runId)            // GET /archive/{id} → ArchivedRunRecord
dashboardApi.restoreArchivedRun(runId)     // POST /archive/{id}/restore
dashboardApi.deleteArchivedRun(runId)      // DELETE /archive/{id}
```

**Error Handling:** Throws `HttpError(status, message)` or `ParseError(url, zodError)`.

---

## 7. Type Registry (`apps/frontend/src/lib/types.ts`)

**Envelope Union Types:**
- `AgentEventEnvelope`: `{ type: "agent_event", run_id, agent_path, kind: "start"|"end"|"error"|"chunk", input?, output?, started_at, finished_at?, metadata, error? }`
- `AlgoEventEnvelope`: `{ type: "algo_event", run_id, algorithm_path, kind: string, payload, started_at, finished_at?, ... }`
- `SlotOccupancyEnvelope`, `CostUpdateEnvelope`, `StatsUpdateEnvelope` – also SSE types

**Key Response Types:**
- `RunSummary`: id, started_at, last_event_at, state, has_graph, is_algorithm, algorithm_path, root_agent_path, script, event_counts, event_total, duration_ms, generations[], iterations[], rounds[], candidates[], batches[], prompt/completion tokens, error, algorithm_terminal_score, cost?, synthetic, parent_run_id, algorithm_class
- `AgentMetaResponse`: agent_path, class_name, kind, hash_content, role?, task?, rules, examples, config, input_schema?, output_schema?, forward_in/out_overridden, trainable_paths, langfuse_search_url
- `RunInvocation`: id, started_at, finished_at?, latency_ms?, prompt/completion_tokens?, cost_usd?, hashes (model, prompt, graph, input, output_schema, config, content), status, error?, langfuse_url?, script, backend?, model?, renderer?, input?, output?
- `IoGraphResponse`: root, nodes (with fields), edges (with agent_path, class_name, kind)
- `AgentInvocationsResponse`: agent_path, invocations: AgentInvocation[]
- `FitnessEntry`: gen_index, best, mean, worst, train_loss?, val_loss?, population_scores[], timestamp
- `MutationsMatrix`: gens, ops, success[][], attempts[][]
- `DriftEntry`: epoch, before_text, after_text, selected_path, changes[], critique, gradient_epoch?, changed_params, delta_count, timestamp
- `ProgressSnapshot`: epoch, epochs_total?, batch, batches_total?, elapsed_s, rate_batches_per_s, eta_s?, finished
- `Generation`: gen_index?, best?, mean?, scores[], survivor_indices[], op_attempt/success_counts, timestamp
- `Iteration`: iter_index?, phase?, score?, text?, metadata, timestamp
- `Round`: round_index?, scores[], timestamp
- `Candidate`: iter_index?, candidate_index?, score?, text?, timestamp

---

## 8. Tailwind / CSS Tokens

**File:** `apps/frontend/src/styles/tokens.css`

**CSS Custom Properties (theme variables):**
```css
--color-bg:              #0a0c12  /* dark base */
--color-bg-1:            #12151e  /* surface */
--color-bg-2:            #181c28  /* input/card bg */
--color-bg-3:            #1f2432  /* hover/selected */
--color-border:          #262c3b
--color-border-strong:   #313849
--color-text:            #e7e9f1
--color-muted:           #8991a7
--color-muted-2:         #5a6275
--color-accent:          #46a7ff  /* blue */
--color-accent-dim:      #264b72  /* blue background */
--color-ok:              #43c871  /* green */
--color-ok-dim:          #1c3d27
--color-warn:            #f2a93a  /* orange */
--color-err:             #ff6b7a  /* red */
--color-err-dim:         #4a1c23
--color-algo:            #b794f4  /* purple */
--color-chunk:           #778bae  /* blue-gray */

--font-sans:  -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif
--font-mono:  ui-monospace, "SF Mono", Menlo, Consolas, monospace
```

**Tailwind Config:** Uses `@tailwindcss/vite` v4.0.0 in vite config. Custom theme comes from `@theme` block in tokens.css. No separate tailwind.config.ts.

---

## 9. package.json Dependencies

**React & Routing:**
- `react@19.0.0`, `react-dom@19.0.0`
- `react-router-dom@7.0.0` (v7 with createBrowserRouter)

**State & Data:**
- `zustand@5.0.0` (stores)
- `@tanstack/react-query@5.59.0` (server state)
- `zod@3.23.0` (schema validation)

**UI & Rendering:**
- `class-variance-authority@0.7.0` (CVA for variant styling)
- `clsx@2.1.0` (className utilities)
- `tailwindcss@4.0.0`, `@tailwindcss/vite@4.0.0`
- `tailwind-merge@2.5.0`
- `lucide-react@0.460.0` (icons)
- `@radix-ui/react-slider@1.2.0`, `@radix-ui/react-tabs@1.1.0`, `@radix-ui/react-tooltip@1.1.0`

**JSON Rendering:**
- `@json-render/core@0.1.0`
- `@json-render/react@0.1.0`

**Charting & Visualization:**
- `recharts@2.13.0`
- `@xyflow/react@12.8.6` (formerly react-flow)
- `@dagrejs/dagre@1.1.5` (graph layout)
- `mermaid@11.4.0`
- `framer-motion` – NOT present (would need to add for advanced animations)

**Virtual Lists:**
- `@tanstack/react-virtual@3.13.24`

**Test & Build:**
- `vitest@2.1.0`, `@testing-library/react@16.1.0`, `@testing-library/dom@10.4.0`, `happy-dom@15.0.0`
- `vite@5.4.0`, `@vitejs/plugin-react@4.3.0`
- `typescript@5.6.0`
- `@biomejs/biome@1.9.0` (linter/formatter)

**Missing for Redesign (if needed):**
- `framer-motion` – for smooth transitions/drawer animations
- `@headlessui/react` – additional unstyled components (if expanding beyond current set)

---

## 10. Test Infrastructure

**Test Runner:** Vitest v2.1.0  
**Test Library:** @testing-library/react v16.1.0 + happy-dom  
**Pattern (from `pin-indicator.test.tsx`):**

```typescript
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";

describe("<Component />", () => {
  beforeEach(() => {
    // setup (e.g., clear store state)
  });
  afterEach(() => {
    cleanup();  // unmount all
  });

  it("renders with expected aria-label", () => {
    render(<Component />);
    expect(screen.getByRole("button", { name: "label" })).toBeDefined();
  });

  it("handles click events", () => {
    render(<Component />);
    fireEvent.click(screen.getByRole("button"));
    // assert state/side-effect
  });
});
```

**Command:** `npm run test` (run once), `npm run test:watch` (watch mode)

---

## 11. Backend Routes (`apps/dashboard/operad_dashboard/`)

### Core App (`app.py`)
**Key Endpoints:**

| Route | Method | Response | Notes |
|-------|--------|----------|-------|
| `/api/manifest` | GET | `{ mode, version, langfuseUrl, allowExperiment }` | Feature flags |
| `/runs` | GET | `RunSummary[]` | Query: `?include=synthetic` |
| `/runs/{id}/summary` | GET | `RunSummary` | + cost totals |
| `/runs/{id}/events` | GET | `{ run_id, events[] }` | Query: `?limit=N` (max 500) |
| `/runs/{id}/children` | GET | `RunSummary[]` | Synthetic children |
| `/runs/{id}/parent` | GET | `RunSummary` | Parent of synthetic run |
| `/runs/{id}/tree` | GET | `{ root, children[] }` | Subtree snapshot |
| `/graph/{id}` | GET | `{ mermaid }` | Mermaid graph string |
| `/stats` | GET | `GlobalStats` | event/token totals, subscriber count |
| `/evolution` | GET | `{ generations }` | Cross-run algo data |
| `/stream` | GET | EventSourceResponse | SSE: agent_event, algo_event, cost_update, stats_update |
| `/_ingest` | POST | `{ ok: true }` | HTTP envelope ingest |

### Agent Routes (`agent_routes.py`)

| Route | Method | Response | Notes |
|-------|--------|----------|-------|
| `/runs/{id}/io_graph` | GET | `IoGraphResponse` | root + nodes (type defs) + edges (agent paths) |
| `/runs/{id}/invocations` | GET | `RunInvocationsResponse` | Top-level (all agents) |
| `/runs/{id}/agent/{path}/meta` | GET | `AgentMetaResponse` | Class, kind, config, schemas, examples, rules |
| `/runs/{id}/agent/{path}/invocations` | GET | `AgentInvocationsResponse` | Invocation rows for agent |
| `/runs/{id}/agent/{path}/parameters` | GET | `AgentParametersResponse` | Trainable params + gradients |
| `/runs/{id}/agent/{path}/values` | GET | `AgentValuesResponse` | Query: `?attr=X.Y&side=in\|out` |
| `/runs/{id}/agent/{path}/prompts` | GET | `AgentPromptsResponse` | Prompt versions + diffs |
| `/runs/{id}/agent/{path}/events` | GET | `AgentEventsResponse` | Filtered events; Query: `?limit=N` |
| `/runs/{id}/agent/{path}/diff` | GET | `AgentInvocationDiffResponse` | Query: `?from=ID&to=ID` |
| `/runs/{id}/agent/{path}/invoke` | POST | `AgentInvokeResponse` | Body: `{ input, overrides?, stream }` |

### Panel Routes (in `routes/` subdirectory)

**fitness.py**
- `GET /runs/{id}/fitness.json` → `FitnessEntry[]`

**mutations.py**
- `GET /runs/{id}/mutations.json` → `MutationsMatrix { gens, ops, success[][], attempts[][] }`

**drift.py**
- `GET /runs/{id}/drift.json` → `DriftEntry[]` – param change timeline

**progress.py**
- `GET /runs/{id}/progress.json` → `ProgressSnapshot` – training/sweep progress

**iterations.py**
- `GET /runs/{id}/iterations.json` → `IterationsResponse { iterations[], max_iter?, threshold? }`

**debate.py**
- `GET /runs/{id}/debate.json` → `DebateRoundsResponse` – rounds of proposals/critiques

**checkpoints.py, gradients.py, sweep.py, cassettes.py, benchmarks.py, archive.py**  
– Similar pattern per endpoint name.

---

## 12. Key Data Structures

### RunInfo (Python backend, `runs.py`)
In-memory LRU bounded to 100 runs. Each holds:
- Event deque (capped per run)
- Event counts by kind
- Generations, iterations, rounds, candidates, batches arrays
- Mermaid graph + graph_json
- Algorithm metadata (path, kinds, terminal score)
- Root agent path, script, token totals

### WebDashboardObserver (`observer.py`)
Receives operad.runtime events → serializes as envelopes (JSON) → broadcasts to SSE clients.

---

## 13. Development Workflow

**Frontend Build:**
```bash
# Dev server
npm run dev:dashboard          # port 5173, proxies /runs, /graph, /stream to :7860
npm run dev:studio           # port 5174

# Build
npm run build                 # builds both dashboard & studio

# Tests
npm run test                  # vitest
npm run test:watch
npm run test:e2e             # playwright
```

**Backend (Python, :7860):**
```bash
uvicorn operad_dashboard.app:app --port 7860
```

**Vite Proxies:**
- `/runs/*` → `:7860`
- `/graph/*` → `:7860`
- `/stream` → `:7860`
- `/stats`, `/evolution`, `/_ingest` → `:7860`
- `/api/*` → `:7860` (dashboard) or `:7870` (studio)
- `/jobs/*` → `:7870` (studio only)

---

## 14. Redesign Checklist

**Before touching the UI:**

1. ✓ Understand the 11 UI components and their props (sections 1, 8).
2. ✓ Understand `@json-render` flow: layout JSON → DashboardRenderer → resolved props → uiRegistry components (section 2).
3. ✓ Know the routing structure and how to add `/runs/:runId/graph`, `/runs/:runId/invocations` sub-routes (section 3).
4. ✓ Understand drawer state in `useUIStore` (section 4); you'll need to refactor `drawer.kind` logic.
5. ✓ Query keys are stable in TanStack Query; check `useRuns`, `useRunSummary`, etc. for cache invalidation (section 5, 6).
6. ✓ Zod schemas define all wire shapes; if backend changes, update `types.ts` (section 7).
7. ✓ CSS custom properties are theme tokens; extend in `tokens.css` or adjust Tailwind theme (section 8).
8. ✓ All tests use vitest + testing-library (section 10).
9. ✓ Backend routes are FastAPI + Pydantic (section 11); add new endpoints as `@router.get(...)` in agent_routes.py, then wire in app.py.

**Common Tasks:**

- **New panel UI:** Add component to `components/ui/`, export from `index.ts`, register in `uiRegistry` if it's layout-driven.
- **New hook:** Follow queryKey pattern from `use-runs.ts`; ensure Zod schema exists in `types.ts`.
- **New route:** Add to `dashboardRoutes` in `routes.tsx`; create page component in `pages/`.
- **New store:** Use zustand's `create()`, optional `persist()` middleware; export from `stores/index.ts`.
- **New endpoint:** Add `@router.get(...)` in agent_routes.py, add Zod schema to `types.ts`, add method to `dashboardApi`, call from hook.

---

## 15. Notable Patterns

- **Layout-driven UI:** Components are serialized JSON → DashboardRenderer resolves props → uiRegistry maps to React → browser renders. No code-gen; definition lives in Python backend or JSON files.
- **Bounded stores:** Both event buffer and run registry have hard caps (500 events/run, 100 runs) to prevent unbounded growth on long sessions.
- **Per-run versioning:** Hashes (model, prompt, graph, config, content) allow diffing invocations without storing entire payloads.
- **Agent path encoding:** Paths use `{path:path}` in FastAPI and `encodeURIComponent()` in client to handle dots and special chars.
- **Synthetic runs:** Child runs of algorithms marked with `synthetic=true`, parent_run_id linked; hidden by default in `/runs` list.
- **SSE multiplexing:** Single `/stream` endpoint broadcasts all envelope types (agent_event, algo_event, stats_update, cost_update); consumer routes via envelope.type.
- **Query key scoping:** TanStack keys are tuples: `["run", "summary", runId]`, `["run", "events", runId, limit]`, etc. Enables precise cache invalidation (e.g., invalidate only `["runs"]` on reconnect).

