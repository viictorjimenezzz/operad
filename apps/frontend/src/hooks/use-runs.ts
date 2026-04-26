import { dashboardApi } from "@/lib/api/dashboard";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useRuns() {
  return useQuery({
    queryKey: ["runs"] as const,
    queryFn: () => dashboardApi.runs(),
  });
}

export function useRunsFiltered(includeSynthetic: boolean) {
  return useQuery({
    queryKey: ["runs", { includeSynthetic }] as const,
    queryFn: () => dashboardApi.runsWithParams({ includeSynthetic }),
    refetchInterval: 5_000,
  });
}

export function useRunSummary(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "summary", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useRunSummary: runId is required");
      return dashboardApi.runSummary(runId);
    },
    enabled: !!runId,
  });
}

export function useRunEvents(runId: string | null | undefined, limit = 500) {
  return useQuery({
    queryKey: ["run", "events", runId, limit] as const,
    queryFn: () => {
      if (!runId) throw new Error("useRunEvents: runId is required");
      return dashboardApi.runEvents(runId, limit);
    },
    enabled: !!runId,
  });
}

export function useRunInvocations(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "invocations", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useRunInvocations: runId is required");
      return dashboardApi.runInvocations(runId);
    },
    enabled: !!runId,
  });
}

export function useAgentMeta(
  runId: string | null | undefined,
  agentPath: string | null | undefined,
) {
  return useQuery({
    queryKey: ["run", "agent-meta", runId, agentPath] as const,
    queryFn: () => {
      if (!runId) throw new Error("useAgentMeta: runId is required");
      if (!agentPath) throw new Error("useAgentMeta: agentPath is required");
      return dashboardApi.agentMeta(runId, agentPath);
    },
    enabled: !!runId && !!agentPath,
  });
}

export function useAgentValues(
  runId: string | null | undefined,
  agentPath: string | null | undefined,
  attr: string | null | undefined,
  side: "in" | "out",
) {
  return useQuery({
    queryKey: ["run", "agent-values", runId, agentPath, attr, side] as const,
    queryFn: () => {
      if (!runId) throw new Error("useAgentValues: runId is required");
      if (!agentPath) throw new Error("useAgentValues: agentPath is required");
      if (!attr) throw new Error("useAgentValues: attr is required");
      return dashboardApi.agentValues(runId, agentPath, attr, side);
    },
    enabled: !!runId && !!agentPath && !!attr,
  });
}

export function useGraph(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "graph", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useGraph: runId is required");
      return dashboardApi.graph(runId);
    },
    enabled: !!runId,
    staleTime: 60_000,
  });
}

export function useFitness(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "fitness", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useFitness: runId is required");
      return dashboardApi.fitness(runId);
    },
    enabled: !!runId,
  });
}

export function useMutations(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "mutations", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useMutations: runId is required");
      return dashboardApi.mutations(runId);
    },
    enabled: !!runId,
  });
}

export function useDrift(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "drift", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useDrift: runId is required");
      return dashboardApi.drift(runId);
    },
    enabled: !!runId,
  });
}

export function useProgress(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["run", "progress", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useProgress: runId is required");
      return dashboardApi.progress(runId);
    },
    enabled: !!runId,
  });
}

export function useBenchmarks() {
  return useQuery({
    queryKey: ["benchmarks"] as const,
    queryFn: () => dashboardApi.benchmarks(),
  });
}

export function useBenchmarkDetail(benchmarkId: string | null | undefined) {
  return useQuery({
    queryKey: ["benchmarks", benchmarkId] as const,
    queryFn: () => {
      if (!benchmarkId) throw new Error("useBenchmarkDetail: benchmarkId is required");
      return dashboardApi.benchmarkDetail(benchmarkId);
    },
    enabled: !!benchmarkId,
  });
}

export function useBenchmarkTag() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ benchmarkId, tag }: { benchmarkId: string; tag: string }) =>
      dashboardApi.benchmarkTag(benchmarkId, tag),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["benchmarks"] });
      queryClient.invalidateQueries({ queryKey: ["benchmarks", vars.benchmarkId] });
    },
  });
}

export function useBenchmarkDelete() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (benchmarkId: string) => dashboardApi.benchmarkDelete(benchmarkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["benchmarks"] });
    },
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"] as const,
    queryFn: () => dashboardApi.stats(),
    refetchInterval: 5_000,
  });
}

export function useEvolution() {
  return useQuery({
    queryKey: ["evolution"] as const,
    queryFn: () => dashboardApi.evolution(),
  });
}

export function useManifest() {
  return useQuery({
    queryKey: ["manifest"] as const,
    queryFn: () => dashboardApi.manifest(),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}

export function useArchiveRuns(params: {
  from?: number;
  to?: number;
  algorithm?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["archive", "list", params] as const,
    queryFn: () => dashboardApi.archive(params),
  });
}

export function useArchivedRun(runId: string | null | undefined) {
  return useQuery({
    queryKey: ["archive", "detail", runId] as const,
    queryFn: () => {
      if (!runId) throw new Error("useArchivedRun: runId is required");
      return dashboardApi.archivedRun(runId);
    },
    enabled: !!runId,
  });
}

export function useRestoreArchivedRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => dashboardApi.restoreArchivedRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.invalidateQueries({ queryKey: ["archive"] });
    },
  });
}

export function useDeleteArchivedRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => dashboardApi.deleteArchivedRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archive"] });
    },
  });
}
