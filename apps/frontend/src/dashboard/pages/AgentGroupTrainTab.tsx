import {
  ParameterEvolution,
  type ParameterSeries,
} from "@/components/agent-view/group/parameter-evolution";
import { DriftBlock } from "@/components/agent-view/overview/drift-block";
import { EmptyState, Metric, PanelSection } from "@/components/ui";
import {
  useAgentGroup,
  useAgentGroupParameters,
  useAgentMeta,
  useDrift,
  useRunInvocations,
} from "@/hooks/use-runs";
import { dashboardApi } from "@/lib/api/dashboard";
import type { AgentParametersResponse, RunSummary } from "@/lib/types";
import { formatNumber } from "@/lib/utils";
import { useQueries } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

export function AgentGroupTrainTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const contracted = useAgentGroupParameters(hashContent);
  const runs = group.data?.runs ?? [];
  const latestRun = runs.at(-1) ?? null;
  const meta = useAgentMeta(latestRun?.run_id ?? null, latestRun?.root_agent_path ?? null);
  const drift = useDrift(latestRun?.run_id);
  const invocations = useRunInvocations(latestRun?.run_id);
  const fallback = useQueries({
    queries: runs.map((run) => ({
      queryKey: ["run", "agent-parameters", run.run_id, run.root_agent_path] as const,
      queryFn: () => dashboardApi.agentParameters(run.run_id, run.root_agent_path ?? ""),
      enabled: Boolean(run.root_agent_path) && !contracted.data,
      retry: false,
    })),
  });

  if (!hashContent || !group.data) return null;
  const series = contracted.data
    ? fromContracted(group.data.runs, contracted.data.series, contracted.data.paths)
    : fromFallback(
        group.data.runs,
        fallback.map((query) => query.data),
      );
  const trainableCount = meta.data?.trainable_paths.length ?? series.length;
  const valuesSeen = series.reduce(
    (acc, item) => acc + new Set(item.points.map((p) => p.hash)).size,
    0,
  );
  const bestScore = bestMetric(group.data.runs);

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-4">
        {series.length === 0 && (drift.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="no trainable parameter history"
            description="this group has no trainable parameters or prompt drift events"
          />
        ) : (
          <>
            <PanelSection label="Training">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2">
                <Metric label="trainable params" value={trainableCount} />
                <Metric label="values seen" value={valuesSeen} />
                <Metric label="drift events" value={drift.data?.length ?? 0} />
                <Metric
                  label="optimizer history"
                  value={group.data.is_trainer ? `trainer/${runs.length}` : "none"}
                />
                <Metric
                  label="best score"
                  value={bestScore == null ? "-" : formatNumber(bestScore)}
                />
              </div>
            </PanelSection>
            <ParameterEvolution series={series} />
            {(drift.data?.length ?? 0) > 0 && latestRun ? (
              <PanelSection label="Drift events" count={drift.data?.length ?? 0}>
                <DriftBlock dataInvocations={invocations.data} runId={latestRun.run_id} />
              </PanelSection>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function fromContracted(
  runs: RunSummary[],
  rows: Array<{ run_id: string; values: Record<string, { value?: unknown; hash: string }> }>,
  paths: string[],
): ParameterSeries[] {
  const byRun = new Map(runs.map((run) => [run.run_id, run]));
  return paths
    .map((path) => ({
      path,
      points: rows
        .filter((row) => row.values[path])
        .map((row) => ({
          runId: row.run_id,
          startedAt: byRun.get(row.run_id)?.started_at ?? 0,
          value: row.values[path]?.value,
          hash: row.values[path]?.hash ?? stableHash(row.values[path]?.value),
        }))
        .sort((a, b) => a.startedAt - b.startedAt),
    }))
    .filter((item) => item.points.length > 0);
}

function fromFallback(
  runs: RunSummary[],
  responses: Array<AgentParametersResponse | undefined>,
): ParameterSeries[] {
  const byPath = new Map<string, ParameterSeries>();
  responses.forEach((response, index) => {
    const run = runs[index];
    if (!response || !run) return;
    for (const param of response.parameters) {
      if (!param.requires_grad) continue;
      const existing = byPath.get(param.path) ?? { path: param.path, points: [] };
      existing.points.push({
        runId: run.run_id,
        startedAt: run.started_at,
        value: param.value,
        hash: stableHash(param.value),
      });
      byPath.set(param.path, existing);
    }
  });
  return [...byPath.values()].map((series) => ({
    ...series,
    points: series.points.sort((a, b) => a.startedAt - b.startedAt),
  }));
}

function stableHash(value: unknown): string {
  const text = JSON.stringify(value);
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(16).padStart(8, "0").slice(0, 16);
}

function bestMetric(runs: RunSummary[]): number | null {
  const values = runs
    .flatMap((run) => [run.algorithm_terminal_score, run.metrics?.best_score, run.metrics?.score])
    .filter((value): value is number => value != null && Number.isFinite(value));
  return values.length > 0 ? Math.max(...values) : null;
}
