import { useQueries } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { usePinnedRunsStore } from "@/stores/pinned-runs";
import type { z } from "zod";
import type { RunSummary } from "@/lib/types";

export const usePinnedRuns = () => usePinnedRunsStore();

export function useIsPinned(runId: string): boolean {
  return usePinnedRunsStore((s) => s.pinned.includes(runId));
}

export function usePinnedRunSummaries():
  | z.infer<typeof RunSummary>[]
  | undefined {
  const pinned = usePinnedRunsStore((s) => s.pinned);
  const unpin = usePinnedRunsStore((s) => s.unpin);

  const results = useQueries({
    queries: pinned.map((id) => ({
      queryKey: ["run", "summary", id] as const,
      queryFn: () => dashboardApi.runSummary(id),
      retry: false,
    })),
  });

  let staleCount = 0;
  results.forEach((r, i) => {
    const id = pinned[i];
    if (r.isError && id !== undefined) {
      unpin(id);
      staleCount++;
    }
  });
  if (staleCount > 0) {
    console.warn(`[pinned-runs] auto-unpinned ${staleCount} stale run(s)`);
  }

  if (results.some((r) => r.isPending)) return undefined;
  return results.filter((r) => r.isSuccess).map((r) => r.data!);
}
