import { EmptyState, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";
import { useAlgorithmGroups } from "@/hooks/use-runs";
import { getAlgorithmMetric } from "@/lib/algorithm-metrics";
import type { RunSummary } from "@/lib/types";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
  { id: "instance", label: "Instance", source: "instance", sortable: true, width: 150 },
  { id: "run", label: "Run ID", source: "_id", sortable: true, width: 220 },
  {
    id: "started",
    label: "Started timestamp",
    source: "started",
    sortable: true,
    defaultSort: "desc",
    width: 170,
  },
  { id: "script", label: "Script", source: "script", sortable: true, width: "1fr" },
  {
    id: "latency",
    label: "Latency",
    source: "_duration",
    sortable: true,
    align: "right",
    width: 82,
  },
  { id: "metric", label: "Metric", source: "metric", sortable: true, align: "right", width: 112 },
  { id: "events", label: "Events", source: "events", sortable: true, align: "right", width: 76 },
  { id: "tokens", label: "Tokens", source: "tokens", sortable: true, align: "right", width: 82 },
  { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 76 },
];

export function AlgorithmsIndexPage() {
  const groups = useAlgorithmGroups();
  const allRuns =
    groups.data?.flatMap((group) =>
      group.runs.map((run) => ({
        ...run,
        algorithm_class: run.algorithm_class ?? group.class_name,
      })),
    ) ?? [];
  const rows = allRuns.map(runToRow);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading algorithms…</div>
        ) : rows.length === 0 ? (
          <EmptyState
            title="no algorithm runs yet"
            description="algorithm invocations will appear here once they emit algorithm events"
          />
        ) : (
          <RunTable
            rows={rows}
            columns={columns}
            storageKey="algorithms-index"
            rowHref={(row) => `/algorithms/${encodeURIComponent(row.id)}`}
            emptyTitle="no algorithm runs yet"
            emptyDescription="algorithm invocations will appear here once they emit algorithm events"
            pageSize={50}
          />
        )}
      </div>
    </div>
  );
}

function runToRow(run: RunSummary): RunRow {
  const className = run.algorithm_class ?? run.algorithm_path?.split(".").at(-1) ?? "Algorithm";
  const tokens = run.prompt_tokens + run.completion_tokens;

  return {
    id: run.run_id,
    identity: className,
    state: run.state,
    startedAt: run.started_at,
    endedAt: run.last_event_at,
    durationMs: run.duration_ms,
    fields: {
      instance: { kind: "text", value: className },
      started: { kind: "text", value: formatTimestamp(run.started_at), mono: true },
      script: { kind: "text", value: run.script ?? "-", mono: true },
      metric: { kind: "text", value: getAlgorithmMetric(run), mono: true },
      events: { kind: "num", value: run.event_total, format: "int" },
      tokens: { kind: "num", value: tokens, format: "tokens" },
      cost: { kind: "num", value: run.cost?.cost_usd ?? 0, format: "cost" },
    },
  };
}

function formatTimestamp(unixSeconds: number): string {
  return new Date(unixSeconds * 1000)
    .toISOString()
    .replace("T", " ")
    .replace(/\.\d{3}Z$/, " UTC");
}
