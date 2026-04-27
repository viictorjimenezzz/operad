import {
  Breadcrumb,
  EmptyState,
  Metric,
  PanelSection,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";
import { useAgentGroups } from "@/hooks/use-runs";
import type { AgentGroupSummary } from "@/lib/types";
import { formatCost, formatTokens } from "@/lib/utils";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 80 },
  { id: "class", label: "Class", source: "class", sortable: true, width: "1fr" },
  { id: "hash", label: "Hash", source: "hash", sortable: true, width: 110 },
  { id: "count", label: "# inv", source: "count", align: "right", sortable: true, width: 70 },
  {
    id: "last",
    label: "Last seen",
    source: "_ended",
    sortable: true,
    defaultSort: "desc",
    width: 90,
  },
  { id: "p50", label: "p50 ms", source: "_duration", align: "right", sortable: true, width: 90 },
  { id: "tokens", label: "Tokens", source: "tokens", align: "right", sortable: true, width: 90 },
  { id: "cost", label: "Cost", source: "cost", align: "right", sortable: true, width: 80 },
  { id: "errors", label: "Errors", source: "errors", align: "right", sortable: true, width: 70 },
  { id: "spark", label: "Latency", source: "spark", width: 80 },
];

export function AgentsIndexPage() {
  const groups = useAgentGroups();
  const data = groups.data ?? [];
  const rows = data.map(groupRow);
  const totalTokens = data.reduce(
    (acc, group) => acc + group.prompt_tokens + group.completion_tokens,
    0,
  );
  const totalCost = data.reduce((acc, group) => acc + group.cost_usd, 0);
  const invocations = data.reduce((acc, group) => acc + group.count, 0);
  const errors = data.reduce((acc, group) => acc + group.errors, 0);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Agents" }]} />
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading agents...</div>
        ) : data.length === 0 ? (
          <EmptyState
            title="no agents yet"
            description="run an agent or replay a cassette to populate this view"
          />
        ) : (
          <div className="space-y-4">
            <PanelSection label="Agents">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2">
                <Metric label="agents" value={data.length} />
                <Metric label="invocations" value={invocations} />
                <Metric label="tokens" value={formatTokens(totalTokens)} />
                <Metric label="cost" value={formatCost(totalCost)} />
                <Metric label="errors" value={errors} />
              </div>
            </PanelSection>
            <RunTable
              rows={rows}
              columns={columns}
              storageKey="agents-index"
              rowHref={(row) => `/agents/${row.id}`}
              emptyTitle="no agents yet"
              emptyDescription="run an agent or replay a cassette to populate this view"
            />
          </div>
        )}
      </div>
    </div>
  );
}

function groupRow(group: AgentGroupSummary): RunRow {
  const state = group.running > 0 ? "running" : group.errors > 0 ? "error" : "ended";
  const tokens = group.prompt_tokens + group.completion_tokens;
  return {
    id: group.hash_content,
    identity: group.hash_content,
    state,
    startedAt: group.first_seen,
    endedAt: group.last_seen,
    durationMs: median(group.latencies),
    fields: {
      class: { kind: "text", value: group.class_name ?? "Agent" },
      hash: { kind: "hash", value: group.hash_content },
      count: { kind: "num", value: group.count, format: "int" },
      tokens: { kind: "num", value: tokens, format: "tokens" },
      cost: { kind: "num", value: group.cost_usd, format: "cost" },
      errors: { kind: "num", value: group.errors, format: "int" },
      spark: { kind: "sparkline", values: group.latencies.slice(-24) },
    },
  };
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? (sorted[mid] ?? null)
    : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
}
