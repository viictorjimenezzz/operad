# 02 — Backbone wiring (LayoutResolver + universal tabs)

**Stage:** 2 (serial; depends on Brief 01; blocks all per-algorithm
briefs)
**Branch:** `dashboard-redesign/02-wiring`
**Depends on:** Brief 01

## Goal

Resurrect the seven orphaned per-algorithm JSON layouts by wiring
`resolveLayout()` into the route table and adding the universal
`Agents` and `Events` tabs to every algorithm layout. After this brief,
`/algorithms/:runId` no longer renders the agent-shaped tabs — it
resolves to the algorithm's own JSON layout. This is the single
highest-leverage change in the redesign.

## Read first

- `proposal.md` §0.1 — the headline finding (every per-algorithm
  layout is dead code).
- `apps/frontend/src/layouts/index.ts` — the existing `resolveLayout()`
  function. Read it; it already does what we need.
- `apps/frontend/src/dashboard/routes.tsx` — the current route table.
- `apps/frontend/src/dashboard/pages/run-detail/RunDetailLayout.tsx`
  — the current generic shell that mounts the wrong tabs everywhere.
- `apps/frontend/src/components/runtime/dashboard-renderer.tsx` — how
  layouts get rendered.
- `apps/frontend/src/lib/layout-schema.ts` — the existing schema (we
  extend it with a first-class `Tabs` element).
- `00-CONTRACTS.md` §1 (Tabs as root element), §9 (route map).
- `INVENTORY.md` §7 (algorithms — what each one does, used to pick
  defaults), §13 (observers — what events drive each tab).

## Files to touch

Create:

- `apps/frontend/src/dashboard/pages/run-detail/AlgorithmDetailLayout.tsx`
  — resolves layout via `resolveLayout(summary.algorithm_path)` and
  renders it with `DashboardRenderer`.
- `apps/frontend/src/dashboard/pages/run-detail/AgentRunDetailLayout.tsx`
  — agent-shaped, replaces `RunDetailLayout` for `/agents/:hash/runs/:runId`.
  Reads the per-tab layouts (§3 below).
- `apps/frontend/src/dashboard/pages/run-detail/TrainingDetailLayout.tsx`
  — Trainer-shaped; resolves to `trainer.json` directly (no class lookup
  because all training runs share the layout).
- `apps/frontend/src/components/agent-view/page-shell/agents-tab.tsx`
  — the **universal Agents tab** component (Brief 15 specifies the
  contents; this brief just wires it).
- `apps/frontend/src/components/agent-view/page-shell/events-tab.tsx`
  — the **universal Events tab** component (Brief 15 specifies the
  contents).
- `apps/frontend/src/dashboard/pages/OPROIndexPage.tsx` — Q7's
  "OPRO own page" entry (Brief 16 owns the actual layout).
- A new `talker_reasoner.json` layout (the only algorithm that lacks
  one today; Brief 09 fills its tab contents).
- A new `auto_researcher.json` layout (same; Brief 12 fills it).
- A new `opro.json` layout (Brief 16 fills it).

Edit:

- `apps/frontend/src/dashboard/routes.tsx` — replace `runDetailChildren`
  with three different layout components per rail. Add `/opro` and
  `/opro/:runId` routes.
- `apps/frontend/src/lib/layout-schema.ts` — add `TabsElement` discrim.
  to the union (tabs are first-class, not a generic `Stack` fallback).
- `apps/frontend/src/components/runtime/dashboard-renderer.tsx` — render
  `Tabs` elements via `Tabs/TabsList/TabsTrigger/TabsContent` from the
  UI primitives, not as a generic stack.
- `apps/frontend/src/components/registry.tsx` — register the universal
  `AgentsTab`, `EventsTab` for JSON-rendered consumption.
- All seven existing per-algorithm layouts to add the universal `Agents`
  + `Events` tabs at the end:
  - `apps/frontend/src/layouts/beam.json`
  - `apps/frontend/src/layouts/debate.json`
  - `apps/frontend/src/layouts/evogradient.json`
  - `apps/frontend/src/layouts/selfrefine.json`
  - `apps/frontend/src/layouts/sweep.json`
  - `apps/frontend/src/layouts/trainer.json`
  - `apps/frontend/src/layouts/verifier.json`

Delete:

- `apps/frontend/src/dashboard/pages/run-detail/RunDetailLayout.tsx`
  (replaced by the three new layouts).
- `apps/frontend/src/dashboard/pages/run-detail/CostTab.tsx` — renamed
  to Metrics by Brief 03; deleted here as part of removing the legacy
  shape.
- `runDetailChildren` array in `routes.tsx`.
- The legacy `/runs/:runId` route entry in `routes.tsx` (no backwards
  compat per `METAPROMPT.md` line 36).

## Route table after this brief

Per `00-CONTRACTS.md` §9. Concretely:

```ts
export const dashboardRoutes = [{
  path: "/",
  element: <Shell />,
  children: [
    { index: true, element: <Navigate to="/agents" replace /> },

    // Agents rail.
    { path: "agents", element: <AgentsIndexPage /> },
    {
      path: "agents/:hashContent",
      element: <AgentGroupPage />,
      children: [
        { index: true, element: <AgentGroupOverviewTab /> },
        { path: "runs", element: <AgentGroupRunsTab /> },
        { path: "metrics", element: <AgentGroupMetricsTab /> },     // renamed
        { path: "train", element: <AgentGroupTrainTab /> },         // conditional
        { path: "graph", element: <AgentGroupGraphTab /> },
      ],
    },
    {
      path: "agents/:hashContent/runs/:runId",
      element: <AgentRunDetailLayout />,                            // new
      children: [
        { index: true, element: <SingleInvocationOverviewTab /> },  // Brief 03
        { path: "graph", element: <SingleInvocationGraphTab /> },
        { path: "metrics", element: <SingleInvocationMetricsTab /> },
        { path: "drift", element: <SingleInvocationDriftTab /> },   // conditional
      ],
    },

    // Algorithms rail.
    { path: "algorithms", element: <AlgorithmsIndexPage /> },
    { path: "algorithms/:runId", element: <AlgorithmDetailLayout /> },

    // Training rail.
    { path: "training", element: <TrainingIndexPage /> },
    { path: "training/:runId", element: <TrainingDetailLayout /> },

    // OPRO rail (Q7).
    { path: "opro", element: <OPROIndexPage /> },
    { path: "opro/:runId", element: <AlgorithmDetailLayout /> },     // resolves opro.json

    // Other rails.
    { path: "benchmarks", element: <BenchmarksPage /> },
    { path: "benchmarks/:benchmarkId", element: <BenchmarkDetailPage /> },
    { path: "cassettes", element: <CassettesPage /> },
    { path: "cassettes/*", element: <CassetteDetailPage /> },
    { path: "experiments", element: <ExperimentsPage /> },
    { path: "*", element: <NotFoundPage /> },
  ],
}];
```

(Note: the AgentGroup* and SingleInvocation* tab components are owned
by Brief 04 and Brief 03 respectively; this brief adds the empty stubs
that those briefs flesh out.)

## `Tabs` as a first-class element

`apps/frontend/src/lib/layout-schema.ts` adds:

```ts
const TabsSpec = z.object({
  type: z.literal("Tabs"),
  props: z.object({
    tabs: z.array(z.object({
      id: z.string(),
      label: z.string(),
      badge: z.union([z.string(), z.number()]).optional(),
      condition: z.string().optional(),   // a $expr that evaluates to truthy
    })),
  }),
  children: z.array(z.string()),
});
```

`dashboard-renderer.tsx` resolves `Tabs` elements specially: it uses
the `Tabs` UI primitive (`apps/frontend/src/components/ui/tabs.tsx`)
to render the strip, syncs the active tab with the URL via
`useSearchParams("tab")`, and only mounts the *active* tab's child
subtree (lazy mount).

When a tab declares `condition`, the resolver evaluates it via
`source-resolver.ts`'s `$expr:` grammar. Falsy → tab is hidden (used
for the Drift / Train / Traceback conditional tabs).

## Universal `Agents` tab

Component `AgentsTab` (`agents-tab.tsx`):

```ts
interface AgentsTabProps {
  /** Required: bind via $context.runId in the JSON layout. */
  runId: string;
}
```

Behavior — full spec in Brief 15. Shape from this brief's perspective:
- Fetches `/runs/:runId/children`.
- Renders a `RunTable` with grouping by inner-agent `hash_content` (so
  the 222-cell sweep collapses into ~1 group of 222 rows of `Reasoner`
  invocations). User can toggle "ungroup" to flatten.
- Each row navigates to `/agents/:hash/runs/:runId`.

## Universal `Events` tab

Component `EventsTab` (`events-tab.tsx`):

```ts
interface EventsTabProps {
  runId: string;
  /** Optional default kind filter. Algorithms set this to their salient
   *  kind (cell for sweep, round for debate, generation for evo, etc.). */
  defaultKindFilter?: string[];
}
```

Behavior — full spec in Brief 15. Replaces the existing free-form
`EventTimeline`. Filterable by kind; keyboard navigation (`j/k`);
deep-links via `?event=<env_index>`.

## Default tab strip per algorithm

Update each existing layout to add the universal tabs. Example
(`beam.json`):

Before:
```json
{ "tabs": [{"id":"candidates",…},{"id":"graph",…},{"id":"events",…}] }
```

After:
```json
{ "tabs": [
  {"id":"overview", "label":"Overview"},
  {"id":"candidates", "label":"Candidates"},
  {"id":"agents", "label":"Agents", "badge": "$expr:count($queries.children)"},
  {"id":"events", "label":"Events", "badge": "$queries.summary.event_total"},
  {"id":"graph", "label":"Graph"}
] }
```

And add `agents` / `events` element entries that point at `AgentsTab` /
`EventsTab` with `runId` bound from `$context.runId`. The `$queries.children`
data source needs a new entry:

```json
"children": { "endpoint": "/runs/$context.runId/children" }
```

Apply analogously to `debate.json`, `evogradient.json`, `selfrefine.json`,
`sweep.json`, `trainer.json`, `verifier.json`. Also add new
`talker_reasoner.json`, `auto_researcher.json`, `opro.json` skeletons
with the same Tabs root and `Agents`/`Events`/`Graph` tabs declared but
their per-class tab elements left as empty `EmptyState` placeholders
(per-algo briefs flesh them out).

## Source-resolver extension

`apps/frontend/src/components/runtime/source-resolver.ts` already
supports `$expr:` calls. Add two new whitelisted helpers:

- `count(arr)` → `arr.length`
- `length(obj)` → `Object.keys(obj).length`

Both are needed for tab badges. Other helpers (`latest`, `pluck`,
`hashes`) are already there.

## Design alternatives

### A1: Where does layout resolution happen?

- **(a)** `AlgorithmDetailLayout` reads `summary.algorithm_path` and
  calls `resolveLayout()` (recommended). Single render path; fastest.
- **(b)** Each route hard-codes its layout (e.g.,
  `/algorithms/:runId` → always `*`). **Reject:** defeats the point of
  per-algorithm layouts.
- **(c)** A higher-order layout-server endpoint (`/runs/:id/layout`,
  which exists but only returns `agent.overview`). **Reject for now:**
  the JSON layouts are static enough that frontend-only resolution is
  fine; revisit if we need per-deploy customization.

### A2: How are conditional tabs hidden?

- **(a)** `condition` field evaluated by `source-resolver` (recommended;
  declarative, fits the JSON-driven model).
- **(b)** Imperative — each layout component decides. **Reject:**
  splits the source of truth.

### A3: Lazy tab mount

- **(a)** Mount only the active tab (recommended). Saves on data
  fetches for inactive panels.
- **(b)** Mount all tabs eagerly. Simpler but wasteful when an
  EvoGradient run has 7 tabs and the user only opens 2.
- **(c)** Mount all tabs but suspend SSE subscriptions until activated.
  Compromise — defer if (a) creates a flicker on tab switch.

## Acceptance criteria

- [ ] `/algorithms/:runId` renders the algorithm-specific tabs from the
  JSON layout (verified for Beam, Sweep, Debate, EvoGradient by visiting
  examples 02/04 in the live dashboard).
- [ ] `/training/:runId` renders the Trainer tabs (Loss / Drift /
  Gradients / Checkpoints / Progress / Agents / Events / Graph).
- [ ] `/agents/:hash/runs/:runId` no longer shows the legacy
  Invocations / Cost / Train tabs; it shows the agent-specific shape
  (Overview / Graph / Metrics / Drift?). Brief 03 does the inner
  redesign; this brief just wires the route shape.
- [ ] Universal `Agents` tab is present on every algorithm layout and
  navigates to `/agents/:hash/runs/:runId` for each child.
- [ ] Universal `Events` tab is present on every algorithm layout.
- [ ] `Tabs` is a first-class element type and the renderer mounts
  only the active tab.
- [ ] Tab `condition` works (Drift hidden when no drift events; Train
  hidden when no trainable params; Traceback hidden until Brief 13
  supplies it).
- [ ] URL deep-link `?tab=<id>` opens the right tab on load.
- [ ] Old `/runs/:runId` 404s (or redirects to `/agents`).
- [ ] `pnpm test --run` green.
- [ ] `make build-frontend` green.

## Test plan

- **Unit:** `resolveLayout` already has tests; extend to cover the new
  `talker_reasoner`, `auto_researcher`, `opro` keys.
- **Layout schema:** snapshot test for each per-algorithm JSON to catch
  schema drift.
- **Renderer:** test that Tabs renders only the active subtree; test
  that `condition` hides the right tab.
- **Route:** integration test `routes.test.tsx` for the new routes
  (existing test pattern). Old `/runs/:id` is removed; the test expects
  404.
- **Manual smoke:** open each of `/algorithms/:runId` for examples
  02/04 and verify the tab strip shape.

## Out of scope

- The contents of any per-algorithm tab (Briefs 05-12, 13, 16 own
  those).
- The contents of `Agents` and `Events` tabs (Brief 15 owns those —
  this brief just creates the components and wires them in).
- The single-invocation Overview redesign (Brief 03).
- The agent group page redesign (Brief 04).
- The OPRO emit logic (Brief 16 + Brief 14).

## Hand-off

PR body must include:
1. Diff of `routes.tsx` highlighted.
2. Updated `00-CONTRACTS.md` §9 if any route changed during
   implementation.
3. Confirmation that all 7 existing layouts compile under the new
   `Tabs` schema.
4. A list of any per-algorithm-tab placeholders left for downstream
   briefs to fill (with brief IDs).
