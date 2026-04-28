import {
  Breadcrumb,
  EmptyState,
  Metric,
  PanelSection,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";
import { useAgentClasses, type AgentClassSummary } from "@/hooks/use-runs";
import { formatCost, formatTokens } from "@/lib/utils";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 80 },
  { id: "class", label: "Class", source: "class", sortable: true, width: "1fr" },
  { id: "instances", label: "Instances", source: "instances", align: "right", sortable: true, width: 90 },
  { id: "invocations", label: "Invocations", source: "invocations", align: "right", sortable: true, width: 110 },
  {
    id: "last",
    label: "Last seen",
    source: "_ended",
    sortable: true,
    defaultSort: "desc",
    width: 90,
  },
  { id: "running", label: "Running", source: "running", align: "right", sortable: true, width: 90 },
  { id: "errors", label: "Errors", source: "errors", align: "right", sortable: true, width: 70 },
  { id: "tokens", label: "Tokens", source: "tokens", align: "right", sortable: true, width: 100 },
  { id: "cost", label: "Cost", source: "cost", align: "right", sortable: true, width: 90 },
];

export function AgentsIndexPage() {
  const classes = useAgentClasses();
  const data = classes.data ?? [];
  const rows = data.map(classRow);
  const totalTokens = data.reduce(
    (acc, group) => acc + group.instances.reduce((sum, instance) => sum + instance.prompt_tokens + instance.completion_tokens, 0),
    0,
  );
  const totalCost = data.reduce(
    (acc, group) => acc + group.instances.reduce((sum, instance) => sum + instance.cost_usd, 0),
    0,
  );
  const instances = data.reduce((acc, group) => acc + group.instance_count, 0);
  const invocations = data.reduce(
    (acc, group) => acc + group.instances.reduce((sum, instance) => sum + instance.count, 0),
    0,
  );
  const errors = data.reduce(
    (acc, group) => acc + group.instances.reduce((sum, instance) => sum + instance.errors, 0),
    0,
  );

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Agents" }]} />
      <div className="flex-1 overflow-auto p-4">
        {classes.isLoading ? (
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
                <Metric label="classes" value={data.length} />
                <Metric label="instances" value={instances} />
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
              rowHref={(row) => `/agents/_class_/${encodeURIComponent(row.id)}`}
              emptyTitle="no agents yet"
              emptyDescription="run an agent or replay a cassette to populate this view"
            />
          </div>
        )}
      </div>
    </div>
  );
}

function classRow(group: AgentClassSummary): RunRow {
  const running = group.instances.reduce((sum, instance) => sum + instance.running, 0);
  const errors = group.instances.reduce((sum, instance) => sum + instance.errors, 0);
  const invocations = group.instances.reduce((sum, instance) => sum + instance.count, 0);
  const promptTokens = group.instances.reduce((sum, instance) => sum + instance.prompt_tokens, 0);
  const completionTokens = group.instances.reduce((sum, instance) => sum + instance.completion_tokens, 0);
  const cost = group.instances.reduce((sum, instance) => sum + instance.cost_usd, 0);
  const state = running > 0 ? "running" : errors > 0 ? "error" : "ended";
  const latencies = group.instances.flatMap((instance) => instance.latencies);
  return {
    id: group.class_name,
    identity: group.class_name,
    state,
    startedAt: group.first_seen,
    endedAt: group.last_seen,
    durationMs: median(latencies),
    fields: {
      class: { kind: "hash", value: group.class_name },
      instances: { kind: "num", value: group.instance_count, format: "int" },
      invocations: { kind: "num", value: invocations, format: "int" },
      running: { kind: "num", value: running, format: "int" },
      errors: { kind: "num", value: errors, format: "int" },
      tokens: { kind: "num", value: promptTokens + completionTokens, format: "tokens" },
      cost: { kind: "num", value: cost, format: "cost" },
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
