# 2-2 — Renderer + backfill + SSE coherence

> **Iteration**: 2 of 4. **Parallel slot**: 2.
> **Owns**: the layout renderer, data hooks, and registry plumbing.
> **Forbidden**: the runs list (2-1), pinned-runs (2-3), any layout
> JSON content, any chart component, backend code.

## Problem

The SPA renders per-algorithm dashboards by reading JSON layout files
in `apps/frontend/src/layouts/`. Each layout declares data sources
(`.sse` SSE streams, `.json` snapshot endpoints, `$run.summary`,
`$run.events`, etc.) that get wired into components by
`<DashboardRenderer>`.

Three structural issues:

1. **No backfill on mount**. The renderer subscribes to SSE streams
   for live updates but never fetches the corresponding `.json`
   snapshot first. Result: when you click into a completed run, every
   panel shows "waiting for events…" forever.

   This is the same failure pattern as the legacy HTML's evolution
   tab (the "all runs (live)" mode) which I observed empirically:
   full data exists in the registry, the panel renders empty.

2. **Layouts are not auto-discovered**. Today the catalog has
   hardcoded imports. Adding a new layout (Sweep in 3-3, VerifierLoop
   in 3-4) requires editing the catalog, which becomes a parallel-edit
   conflict in iter-3.

3. **Algorithm-path → layout dispatch is brittle**. Today's logic is
   approximately "exact match `algorithm_path` → use that layout, else
   `default.json`". But algorithm paths look like
   `"EvoGradient"` and `"Trainer"`, and we'll soon have Sweep,
   VerifierLoop, etc.

## Scope

### Owned files

- `apps/frontend/src/components/DashboardRenderer.tsx`
- `apps/frontend/src/hooks/use-event-stream.ts`
- `apps/frontend/src/hooks/use-panel-stream.ts`
- `apps/frontend/src/registry/catalog.ts` and any sibling registry files.
- `apps/frontend/src/layouts/index.ts` (auto-discovery entry).
- New: `apps/frontend/src/lib/data-source.ts` — a small module that
  defines the data-source merge semantics.
- Tests under `apps/frontend/src/components/*.test.tsx` and
  `apps/frontend/src/lib/*.test.ts`.

### Forbidden files

- Any `apps/frontend/src/layouts/*.json` content (each algorithm agent
  in iter-3 owns its own layout). You may, however, define a
  *schema* / typescript type for layouts.
- Any chart component under `apps/frontend/src/shared/charts/`.
- Any panel under `apps/frontend/src/shared/panels/`.
- The runs list (2-1).
- The pinned-runs store (2-3).
- Backend code.

## Direction

### Backfill model

For each `.sse` data source declared in a layout:

1. On mount, fire `fetch('<endpoint>.json')` and merge result into the
   panel's state.
2. Subscribe to `<endpoint>.sse` and merge incoming deltas.
3. On panel unmount, close the SSE.

Decide the merge semantics per data-source shape:

- Lists (fitness entries, drift entries): append, dedupe by primary
  key (`gen_index`, `epoch`, etc.).
- Scalars (progress snapshot): replace.
- Maps (mutation matrix): merge by key.

Type the merge functions strictly. A useful pattern:

```ts
type DataSource<T> = {
  json: () => Promise<T>;
  sse:  (onDelta: (d: T) => void) => () => void;
  merge: (current: T, delta: T) => T;
};
```

### Layout auto-discovery

Use `import.meta.glob('../layouts/*.json', { eager: true })` to
collect every layout JSON at build time. Build a `LayoutResolver`:

```ts
function resolveLayout(algorithmPath: string | null): LayoutSpec {
  // exact match -> prefix match -> default
}
```

This way iter-3 agents drop new JSON files into `layouts/` without
touching anything else.

### Layout schema

Formalize the layout JSON shape as a TypeScript type (and optionally a
zod schema for runtime validation). Today the layout has:

- `dataSources: { [name]: { type: "sse" | "json" | ..., url: string }}`
- `tree: UITree` — passed to `<Renderer>` from `@json-render/react`.

Document it (in a `LayoutSpec.ts` file inside `registry/`) so iter-3
agents know what shape they're producing.

### "All runs (live)" mode

The legacy HTML's "all runs (live)" feature was a global SSE that
emitted generation events as they happened across runs. The SPA
should support this as a *separate* layout (e.g. a
`/global-activity` route or a panel on the home page) — but that's
out of scope here. **Just fix the per-run backfill**; don't worry
about the global view in this task.

### Renderer state isolation

Currently `DashboardRenderer` opens one TanStack Query per data
source. That's fine; verify that:

- Switching between runs cleanly tears down the previous run's SSE
  subscriptions (no leaked event listeners).
- Concurrent runs viewed in two tabs don't share state.
- The TanStack Query `staleTime` for `.json` snapshots is high
  (30s+) since we then live-merge SSE deltas.

### Reconnection

If the dashboard SSE disconnects mid-stream:

- Reconnect with exponential backoff.
- On reconnect, **re-fetch the JSON snapshot** to backfill anything
  missed during the disconnect, then resume SSE.

This is just disciplined HTTP plumbing, but it's the difference
between a flaky-feeling dashboard and a solid one.

## Acceptance criteria

1. Click into a completed run → every panel populates immediately
   (within one fetch round-trip).
2. Watch a live demo → panels update via SSE without re-fetching
   JSON.
3. Drop a new file `apps/frontend/src/layouts/example.json` →
   navigate to a run with `algorithm_path="Example"` → the new layout
   renders without any other code changes.
4. Disconnect network mid-run, reconnect → panel state is consistent
   with the registry state (no missed deltas).
5. Tests:
   - `data-source.test.ts`: merge semantics for lists/scalars/maps.
   - `LayoutResolver.test.ts`: exact / prefix / default fallback.
   - `DashboardRenderer.test.tsx`: backfill-then-stream behavior with
     mocked endpoints.

## Dependencies & contracts

### Depends on

- 1-2: every `.sse` endpoint has a `.json` sibling. Verify this is
  the case for `fitness`, `mutations`, `drift`, `progress`. If any
  gaps exist, raise them in the PR description (don't fix them — that's
  1-2's territory after this lands or a follow-up task).

### Exposes

- A documented `LayoutSpec` type and `<DashboardRenderer>` API that
  iter-3 agents use to author new layouts.
- A `useDataSource(name, runId)` (or similar) hook that any chart
  component can consume to get backfilled-then-streamed data.

## Direction notes / SOTA hints

- TanStack Query already does dedupe + cache. Use its `useQuery` for
  `.json` and a custom subscription that calls `queryClient.setQueryData`
  on SSE deltas — this avoids state-store fragmentation.
- For SSE: native `EventSource` is fine; `@microsoft/fetch-event-source`
  if you need POST-based SSE (you don't here).
- Layout JSON validation: `zod` is in the lockfile if you want runtime
  validation on top of TS types.

## Risks / non-goals

- Don't redesign `@json-render/react`. Just wire data correctly into it.
- Don't introduce Redux or another store; Zustand + TanStack Query are
  enough.
- Don't change SSE serialization. The backend's envelope shape is the
  contract.
- Don't add a "global activity" view; out of scope.

## Verification checklist

- [ ] Demo run, then refresh dashboard → run-detail panels populate
      from JSON snapshot before any new SSE event arrives.
- [ ] New layout JSON drops in without touching the catalog.
- [ ] Disconnect/reconnect smoke test passes.
- [ ] `make frontend-test` and `make frontend-typecheck` pass.
- [ ] No references to the old hardcoded layout imports remain.
