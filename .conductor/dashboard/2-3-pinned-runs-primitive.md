# 2-3 — Pinned-runs primitive

> **Iteration**: 2 of 4. **Parallel slot**: 3.
> **Owns**: a NEW Zustand slice for pinning runs and a small UI
> indicator.
> **Forbidden**: anything not listed below.

## Problem

Iteration 4-1 will introduce a cross-run comparison page at
`/experiments?runs=a,b,c`. Users navigate there from the runs list.
For ergonomics:

- Pin/unpin runs from anywhere (run list, run detail header).
- Pinned runs persist across page reloads.
- The runs list and run detail header both surface a star indicator.

Today there is no pinned-runs concept in the codebase.

This task introduces the primitive. It produces NEW files only — zero
chance of conflict with other iter-2 agents.

## Scope

### Owned files (all NEW)

- `apps/frontend/src/stores/pinned-runs.ts` — Zustand slice.
- `apps/frontend/src/hooks/use-pinned-runs.ts` — convenience hook.
- `apps/frontend/src/shared/ui/pin-indicator.tsx` — star button.
- `apps/frontend/src/stores/pinned-runs.test.ts`
- `apps/frontend/src/shared/ui/pin-indicator.test.tsx`

### Forbidden files

- Anything that exists. **NEW files only.**
- Don't update the runs list (2-1 imports your work).
- Don't update the run detail header (3-5 will).
- Don't add a route for `/experiments` (4-1 will).

## Direction

### Store shape

Suggested API:

```ts
interface PinnedRunsState {
  pinned: Set<string>;
  pin: (runId: string) => void;
  unpin: (runId: string) => void;
  toggle: (runId: string) => void;
  clear: () => void;
  isPinned: (runId: string) => boolean;
}
```

Persist to `localStorage` under a stable key (`operad:pinned-runs:v1`).
Use Zustand's `persist` middleware (already in the lockfile if Zustand
is). Cap to 20 pinned runs; reject pin if at cap (return false from
`pin()`).

### Hook

```ts
function usePinnedRuns(): PinnedRunsState
function useIsPinned(runId: string): boolean  // selector for perf
```

### `<PinIndicator />`

A small star/pin icon button that:

- Receives `runId: string`, `size?: 'sm' | 'md'`.
- Calls `toggle(runId)` on click.
- Renders filled vs outline based on `isPinned`.
- Has an accessible `aria-label="Pin run"` / `"Unpin run"`.
- Uses lucide-react icons (already in the lockfile if shadcn is).

### Selectors / derived state

Add a selector hook:

```ts
function usePinnedRunSummaries(): RunSummary[] | undefined
```

This fetches summaries for all currently pinned run-ids using
TanStack Query (probably one batched call, or N parallel calls — let
the agent decide). 4-1 will use this as the data layer for the
comparison page.

### Edge cases

- A pinned run-id that no longer exists in `/runs` (e.g. registry
  evicted it after restart). Detect on summary fetch; auto-unpin and
  emit a single "We unpinned X stale runs" toast — or log silently.
- Storage quota: bound at 20 ids and reject above; the localStorage
  payload stays tiny.

## Acceptance criteria

1. The store + hook + indicator render in isolation (test only).
2. Pin survives page reload (localStorage).
3. Unit tests cover: pin/unpin/toggle, cap enforcement, persistence,
   isPinned selector reactivity.
4. The `<PinIndicator />` is keyboard-accessible (Enter/Space toggles).
5. No new dependencies beyond what's in `package.json`.

## Dependencies & contracts

### Depends on

- Nothing from this iteration (NEW files).

### Exposes

- `usePinnedRuns()` for any consumer (2-1 imports it).
- `<PinIndicator runId={…} />` for any consumer.
- `usePinnedRunSummaries()` for 4-1.
- LocalStorage key: `operad:pinned-runs:v1`.

## Direction notes / SOTA hints

- Don't over-engineer with a Set proxy or normalized schema. A plain
  array stored as JSON is fine; convert to Set in-memory.
- Zustand's `subscribeWithSelector` middleware lets `useIsPinned`
  re-render only when its specific id flips.
- Test with `act` from `@testing-library/react` and assert against
  the store directly.

## Risks / non-goals

- No server-side persistence. localStorage only.
- No cross-tab sync via `BroadcastChannel` unless trivial; if it
  fits in <20 lines, fine; otherwise skip.
- Don't add an "all pins" page yet — 4-1 owns that.

## Verification checklist

- [ ] All tests pass.
- [ ] Indicator renders in storybook-style harness if your repo has
      one (likely not; skip if so).
- [ ] No imports from `dashboard/`, `studio/`, or other features —
      this is a pure primitive.
