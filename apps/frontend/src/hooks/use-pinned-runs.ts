export type PinnedRunsHook = { pinned: Set<string>; toggle: (id: string) => void };

// Stub — stream 2-3 replaces this with a real Zustand-backed implementation.
export function usePinnedRuns(): PinnedRunsHook {
  return { pinned: new Set(), toggle: () => {} };
}
