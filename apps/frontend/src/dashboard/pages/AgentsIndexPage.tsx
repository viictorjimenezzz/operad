import { EmptyState, Metric, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";
import { useAgentGroups } from "@/hooks/use-runs";
import type { AgentGroupSummary } from "@/lib/types";
import { formatCost, formatTokens } from "@/lib/utils";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
  { id: "class", label: "Class", source: "class", sortable: true, width: 150 },
  { id: "instance", label: "Instance", source: "instance", sortable: true, width: "1fr" },
  {
    id: "invocations",
    label: "Invocations",
    source: "invocations",
    align: "right",
    sortable: true,
    width: 88,
  },
  {
    id: "last",
    label: "Last seen",
    source: "_ended",
    sortable: true,
    defaultSort: "desc",
    width: 96,
  },
  { id: "running", label: "Running", source: "running", align: "right", sortable: true, width: 70 },
  { id: "errors", label: "Errors", source: "errors", align: "right", sortable: true, width: 64 },
  { id: "tokens", label: "Tokens", source: "tokens", align: "right", sortable: true, width: 84 },
  { id: "cost", label: "Cost", source: "cost", align: "right", sortable: true, width: 76 },
];

export function AgentsIndexPage() {
  const groups = useAgentGroups();
  const data = groups.data ?? [];
  const rows = data.map(instanceRow);
  const totalTokens = data.reduce(
    (acc, instance) => acc + instance.prompt_tokens + instance.completion_tokens,
    0,
  );
  const totalCost = data.reduce((acc, instance) => acc + instance.cost_usd, 0);
  const invocations = data.reduce((acc, instance) => acc + instance.count, 0);
  const errors = data.reduce((acc, instance) => acc + instance.errors, 0);

  return (
    <div className="flex h-full flex-col overflow-hidden">
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
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2">
              <Metric label="instances" value={data.length} />
              <Metric label="invocations" value={invocations} />
              <Metric label="tokens" value={formatTokens(totalTokens)} />
              <Metric label="cost" value={formatCost(totalCost)} />
              <Metric label="errors" value={errors} />
            </div>
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

function instanceRow(instance: AgentGroupSummary): RunRow {
  const className = instance.class_name ?? "Agent";
  const state = instance.running > 0 ? "running" : instance.errors > 0 ? "error" : "ended";
  return {
    id: instance.hash_content,
    identity: instance.hash_content,
    state,
    startedAt: instance.first_seen,
    endedAt: instance.last_seen,
    durationMs: median(instance.latencies),
    fields: {
      class: { kind: "text", value: className },
      instance: { kind: "hash", value: instance.hash_content },
      invocations: { kind: "num", value: instance.count, format: "int" },
      running: { kind: "num", value: instance.running, format: "int" },
      errors: { kind: "num", value: instance.errors, format: "int" },
      tokens: {
        kind: "num",
        value: instance.prompt_tokens + instance.completion_tokens,
        format: "tokens",
      },
      cost: { kind: "num", value: instance.cost_usd, format: "cost" },
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
