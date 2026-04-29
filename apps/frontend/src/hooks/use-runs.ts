import { dashboardApi } from "@/lib/api/dashboard";
import type { AgentGroupSummary } from "@/lib/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type AgentClassSummary = {
  class_name: string;
  root_agent_path: string | null;
  instance_count: number;
  first_seen: number;
  last_seen: number;
  instances: AgentGroupSummary[];
};

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

export function useAgentGroups() {
  return useQuery({
    queryKey: ["agents"] as const,
    queryFn: () => dashboardApi.agentGroups(),
    refetchInterval: 5_000,
  });
}

export function useAgentClasses() {
  return useQuery({
    queryKey: ["agent-classes"] as const,
    queryFn: async () => {
      try {
        const response = await fetch("/api/agent-classes", {
          headers: { accept: "application/json" },
        });
        if (response.ok) {
          const raw: unknown = await response.json();
          const parsed = parseAgentClasses(raw);
          if (parsed) return parsed;
        }
      } catch {
        // fallback below
      }
      const groups = await dashboardApi.agentGroups();
      return groupAgentClasses(groups);
    },
    refetchInterval: 5_000,
  });
}

export function useAgentGroup(hashContent: string | null | undefined) {
  return useQuery({
    queryKey: ["agents", hashContent] as const,
    queryFn: () => {
      if (!hashContent) throw new Error("useAgentGroup: hashContent is required");
      return dashboardApi.agentGroup(hashContent);
    },
    enabled: !!hashContent,
    refetchInterval: 5_000,
  });
}

export function useAgentGroupMetrics(hashContent: string | null | undefined) {
  return useQuery({
    queryKey: ["agents", hashContent, "metrics"] as const,
    queryFn: () => {
      if (!hashContent) throw new Error("useAgentGroupMetrics: hashContent is required");
      return dashboardApi.agentGroupMetrics(hashContent);
    },
    enabled: !!hashContent,
    retry: false,
  });
}

export function useAgentGroupParameters(hashContent: string | null | undefined) {
  return useQuery({
    queryKey: ["agents", hashContent, "parameters"] as const,
    queryFn: () => {
      if (!hashContent) throw new Error("useAgentGroupParameters: hashContent is required");
      return dashboardApi.agentGroupParameters(hashContent);
    },
    enabled: !!hashContent,
    retry: false,
  });
}

export function useAlgorithmGroups() {
  return useQuery({
    queryKey: ["algorithms"] as const,
    queryFn: () => dashboardApi.algorithmGroups(),
    refetchInterval: 5_000,
  });
}

export function useOPRORuns() {
  return useQuery({
    queryKey: ["opro"] as const,
    queryFn: () => dashboardApi.oproGroups(),
    refetchInterval: 5_000,
  });
}

export function useTrainingGroups() {
  return useQuery({
    queryKey: ["trainings"] as const,
    queryFn: () => dashboardApi.trainingGroups(),
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

export function useAgentParameters(
  runId: string | null | undefined,
  agentPath: string | null | undefined,
) {
  return useQuery({
    queryKey: ["run", "agent-parameters", runId, agentPath] as const,
    queryFn: () => {
      if (!runId) throw new Error("useAgentParameters: runId is required");
      if (!agentPath) throw new Error("useAgentParameters: agentPath is required");
      return dashboardApi.agentParameters(runId, agentPath);
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

export function useAgentEvents(
  runId: string | null | undefined,
  agentPath: string | null | undefined,
  limit = 500,
) {
  return useQuery({
    queryKey: ["run", "agent-events", runId, agentPath, limit] as const,
    queryFn: () => {
      if (!runId) throw new Error("useAgentEvents: runId is required");
      if (!agentPath) throw new Error("useAgentEvents: agentPath is required");
      return dashboardApi.agentEvents(runId, agentPath, limit);
    },
    enabled: !!runId && !!agentPath,
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

export function usePatchRunNotes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, markdown }: { runId: string; markdown: string }) =>
      dashboardApi.patchRunNotes(runId, markdown),
    onSuccess: (data, vars) => {
      queryClient.setQueryData(["run", "summary", vars.runId], (current: unknown) => {
        if (!current || typeof current !== "object") return current;
        return { ...(current as Record<string, unknown>), notes_markdown: data.notes_markdown };
      });
      queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
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

function parseAgentClasses(raw: unknown): AgentClassSummary[] | null {
  if (!Array.isArray(raw)) return null;
  const parsed: AgentClassSummary[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") return null;
    const record = item as Record<string, unknown>;
    const className =
      typeof record.class_name === "string" && record.class_name.trim().length > 0
        ? record.class_name
        : "Agent";
    const firstSeen = asNumber(record.first_seen);
    const lastSeen = asNumber(record.last_seen);
    const instanceCount = asNumber(record.instance_count);
    if (
      firstSeen == null ||
      lastSeen == null ||
      instanceCount == null ||
      !Array.isArray(record.instances)
    ) {
      return null;
    }
    const instances = parseInstances(record.instances);
    if (!instances) return null;
    parsed.push({
      class_name: className,
      root_agent_path: typeof record.root_agent_path === "string" ? record.root_agent_path : null,
      instance_count: instanceCount,
      first_seen: firstSeen,
      last_seen: lastSeen,
      instances,
    });
  }
  return parsed
    .slice()
    .sort(
      (a, b) =>
        b.last_seen - a.last_seen || b.instance_count - a.instance_count || a.class_name.localeCompare(b.class_name),
    );
}

function parseInstances(items: unknown[]): AgentGroupSummary[] | null {
  const instances: AgentGroupSummary[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") return null;
    const record = item as Record<string, unknown>;
    if (
      typeof record.hash_content !== "string" ||
      !Array.isArray(record.run_ids) ||
      !Array.isArray(record.latencies)
    ) {
      return null;
    }
    const runIds = record.run_ids.filter((value): value is string => typeof value === "string");
    const latencies = record.latencies.filter((value): value is number => typeof value === "number");
    instances.push({
      hash_content: record.hash_content,
      class_name: typeof record.class_name === "string" ? record.class_name : null,
      root_agent_path: typeof record.root_agent_path === "string" ? record.root_agent_path : null,
      count: asNumber(record.count) ?? runIds.length,
      running: asNumber(record.running) ?? 0,
      errors: asNumber(record.errors) ?? 0,
      last_seen: asNumber(record.last_seen) ?? 0,
      first_seen: asNumber(record.first_seen) ?? 0,
      latencies,
      prompt_tokens: asNumber(record.prompt_tokens) ?? 0,
      completion_tokens: asNumber(record.completion_tokens) ?? 0,
      cost_usd: asNumber(record.cost_usd) ?? 0,
      run_ids: runIds,
      backends: stringList(record.backends),
      models: stringList(record.models),
      is_trainer: Boolean(record.is_trainer),
      notes_markdown_count: asNumber(record.notes_markdown_count) ?? 0,
    });
  }
  return instances;
}

function groupAgentClasses(groups: AgentGroupSummary[]): AgentClassSummary[] {
  const map = new Map<string, AgentClassSummary>();
  for (const group of groups) {
    const className = group.class_name ?? "Agent";
    const current = map.get(className);
    if (!current) {
      map.set(className, {
        class_name: className,
        root_agent_path: group.root_agent_path,
        instance_count: 1,
        first_seen: group.first_seen,
        last_seen: group.last_seen,
        instances: [group],
      });
      continue;
    }
    current.instance_count += 1;
    current.first_seen = Math.min(current.first_seen, group.first_seen);
    current.last_seen = Math.max(current.last_seen, group.last_seen);
    if (!current.root_agent_path && group.root_agent_path) {
      current.root_agent_path = group.root_agent_path;
    }
    current.instances.push(group);
  }
  return [...map.values()]
    .map((group) => ({
      ...group,
      instances: group.instances.slice().sort((a, b) => b.last_seen - a.last_seen),
    }))
    .sort(
      (a, b) =>
        b.last_seen - a.last_seen || b.instance_count - a.instance_count || a.class_name.localeCompare(b.class_name),
    );
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.length > 0)
    : [];
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
