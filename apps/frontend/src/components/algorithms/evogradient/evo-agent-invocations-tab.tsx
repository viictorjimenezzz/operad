import {
  EmptyState,
  type RunFieldValue,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";
import { useQuery } from "@tanstack/react-query";

interface EvoAgentInvocationsTabProps {
  runId: string;
}

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 84 },
  { id: "gen", label: "Gen", source: "gen", sortable: true, align: "right", width: 64 },
  { id: "individual", label: "Individual", source: "individual", sortable: true, width: 96 },
  { id: "agent", label: "Agent", source: "agent", sortable: true, width: "1fr" },
  { id: "lineage", label: "Lineage", source: "lineage", sortable: true, width: 104 },
  { id: "operator", label: "Operator", source: "operator", sortable: true, width: 128 },
  { id: "score", label: "Score", source: "score", sortable: true, align: "right", width: 104 },
  { id: "latency", label: "Latency", source: "_duration", sortable: true, align: "right", width: 92 },
  { id: "tokens", label: "Tokens", source: "tokens", sortable: true, align: "right", width: 86 },
  { id: "langfuse", label: "Langfuse", source: "langfuse", width: 92 },
];

export function EvoAgentInvocationsTab({ runId }: EvoAgentInvocationsTabProps) {
  const query = useQuery({
    queryKey: ["run", "agent-invocations", runId] as const,
    queryFn: async () => {
      const response = await fetch(`/runs/${runId}/agent-invocations`, {
        headers: { accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText} <- agent-invocations`);
      }
      return parseRows(await response.json());
    },
    enabled: runId.length > 0,
    refetchInterval: 5_000,
  });

  if (query.isLoading) {
    return <div className="p-4 text-xs text-muted">loading agent invocations...</div>;
  }
  if (query.error) {
    return (
      <EmptyState
        title="agent invocations unavailable"
        description="the dashboard could not load nested invocation rows for this EvoGradient run"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={query.data ?? []}
        columns={columns}
        storageKey={`evogradient.agent-invocations.${runId}`}
        pageSize={50}
        emptyTitle="no agent invocations yet"
        emptyDescription="nested agent calls appear after EvoGradient evaluates individuals"
      />
    </div>
  );
}

function parseRows(raw: unknown): RunRow[] {
  const record = isRecord(raw) ? raw : {};
  const invocations = Array.isArray(record.invocations) ? record.invocations : [];
  return invocations.flatMap((item, index) => {
    if (!isRecord(item)) return [];
    const id = stringValue(item.id) ?? `invocation-${index}`;
    const agentPath = stringValue(item.agent_path) ?? "agent";
    const className = stringValue(item.class_name) ?? agentPath.split(".").at(-1) ?? "Agent";
    const promptTokens = numberValue(item.prompt_tokens) ?? 0;
    const completionTokens = numberValue(item.completion_tokens) ?? 0;
    const status = stringValue(item.status) === "error" ? "error" : "ended";
    return [
      {
        id,
        identity: stringValue(item.hash_content) ?? agentPath,
        state: status,
        startedAt: numberValue(item.started_at),
        endedAt: numberValue(item.finished_at),
        durationMs: numberValue(item.latency_ms),
        fields: {
          gen: { kind: "num", value: numberValue(item.gen_index), format: "int" },
          individual: {
            kind: "text",
            value:
              numberValue(item.individual_id) == null ? "-" : String(numberValue(item.individual_id)),
            mono: true,
          },
          agent: { kind: "text", value: className, mono: true },
          lineage: { kind: "text", value: stringValue(item.lineage_id) ?? "-", mono: true },
          operator: { kind: "text", value: stringValue(item.operator) ?? "unknown", mono: true },
          score: { kind: "score", value: numberValue(item.score) },
          tokens: { kind: "num", value: promptTokens + completionTokens, format: "tokens" },
          langfuse: langfuseField(item),
        },
      },
    ];
  });
}

function langfuseField(item: Record<string, unknown>): RunFieldValue {
  const url = stringValue(item.langfuse_url);
  return url ? { kind: "link", label: "open", to: url } : { kind: "text", value: "-" };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
