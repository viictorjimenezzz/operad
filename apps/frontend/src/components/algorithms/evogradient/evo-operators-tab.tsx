import {
  generationPayloads,
  operatorRadarRuns,
  stringValue,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import { MutationHeatmap } from "@/components/charts/mutation-heatmap";
import { OpSuccessTable } from "@/components/charts/op-success-table";
import { OperatorRadar } from "@/components/charts/operator-radar";
import {
  EmptyState,
  PanelCard,
  PanelGrid,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";

interface EvoOperatorsTabProps {
  summary?: unknown;
  mutations?: unknown;
  events?: unknown;
}

const pathColumns: RunTableColumn[] = [
  { id: "path", label: "Path", source: "path", sortable: true, width: "1fr" },
  { id: "topOp", label: "Top op", source: "topOp", sortable: true, width: 140 },
  {
    id: "attempts",
    label: "Attempts",
    source: "attempts",
    sortable: true,
    align: "right",
    width: 88,
  },
  { id: "success", label: "Success", source: "success", sortable: true, align: "right", width: 78 },
  {
    id: "rate",
    label: "Rate",
    source: "rate",
    sortable: true,
    defaultSort: "desc",
    align: "right",
    width: 78,
  },
];

export function EvoOperatorsTab({ summary, mutations, events }: EvoOperatorsTabProps) {
  const rows = pathRows(events);
  const summaryRecord =
    summary && typeof summary === "object" ? (summary as Record<string, unknown>) : null;
  const runId = stringValue(summaryRecord?.run_id) ?? "run";
  const radarRuns = operatorRadarRuns(mutations, runId);

  return (
    <div className="p-4">
      <PanelGrid cols={2} gap="md">
        <PanelCard title="per-op success rate per generation" bodyMinHeight={280}>
          <MutationHeatmap data={mutations} />
        </PanelCard>
        <PanelCard title="operator totals" bodyMinHeight={280}>
          <OpSuccessTable data={mutations} />
        </PanelCard>
        <PanelCard title="operator balance" bodyMinHeight={280}>
          <OperatorRadar runs={radarRuns} height={250} />
        </PanelCard>
        <PanelCard title="target path success" bodyMinHeight={280}>
          {rows.length > 0 ? (
            <RunTable
              rows={rows}
              columns={pathColumns}
              storageKey={`evogradient.paths.${runId}`}
              pageSize={12}
              emptyTitle="no path mutations"
              emptyDescription="generation events did not include mutation path attribution"
            />
          ) : (
            <EmptyState
              title="no path mutations"
              description="generation events did not include mutation path attribution"
            />
          )}
        </PanelCard>
      </PanelGrid>
    </div>
  );
}

function pathRows(events: unknown): RunRow[] {
  const grouped = new Map<
    string,
    { attempts: number; success: number; ops: Map<string, number> }
  >();
  for (const payload of generationPayloads(events)) {
    const mutations = Array.isArray(payload.mutations) ? payload.mutations : [];
    for (const raw of mutations) {
      const record = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : null;
      const path = stringValue(record?.path) ?? "(root)";
      const op = stringValue(record?.op) ?? "unknown";
      const improved = Boolean(record?.improved);
      const current = grouped.get(path) ?? { attempts: 0, success: 0, ops: new Map() };
      current.attempts += 1;
      if (improved) current.success += 1;
      current.ops.set(op, (current.ops.get(op) ?? 0) + 1);
      grouped.set(path, current);
    }
  }

  return [...grouped.entries()].map(([path, stats]) => {
    const rate = stats.attempts > 0 ? stats.success / stats.attempts : 0;
    const topOp =
      [...stats.ops.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] ??
      "unknown";
    return {
      id: path,
      identity: path,
      state: "ended",
      startedAt: null,
      endedAt: null,
      durationMs: null,
      fields: {
        path: { kind: "text", value: path, mono: true },
        topOp: { kind: "text", value: topOp, mono: true },
        attempts: { kind: "num", value: stats.attempts, format: "int" },
        success: { kind: "num", value: stats.success, format: "int" },
        rate: { kind: "num", value: rate, format: "score" },
      },
    };
  });
}
