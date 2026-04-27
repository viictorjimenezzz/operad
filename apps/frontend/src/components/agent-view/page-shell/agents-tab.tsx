import { Button, EmptyState, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";
import { RunSummary as RunSummarySchema } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { z } from "zod";

interface AgentsTabProps {
  runId: string;
}

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
  { id: "agent", label: "Agent", source: "agent", sortable: true, width: "1fr" },
  { id: "run", label: "Run", source: "_id", sortable: true, width: 160 },
  { id: "events", label: "Events", source: "events", sortable: true, align: "right", width: 76 },
  { id: "tokens", label: "Tokens", source: "tokens", sortable: true, align: "right", width: 88 },
  { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 78 },
  { id: "score", label: "Score", source: "score", sortable: true, align: "right", width: 78 },
  { id: "started", label: "Started", source: "_started", sortable: true, width: 110 },
];

export function AgentsTab({ runId }: AgentsTabProps) {
  const children = useQuery({
    queryKey: ["run", "children", runId] as const,
    queryFn: async () => {
      const response = await fetch(`/runs/${runId}/children`);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText} <- /runs/${runId}/children`);
      }
      return z.array(ChildRunSummary).parse(await response.json());
    },
    enabled: runId.length > 0,
  });
  const [grouped, setGrouped] = useState(true);

  const rows = useMemo(() => (children.data ?? []).map(childToRow), [children.data]);

  if (children.isLoading) {
    return <div className="p-4 text-xs text-muted">loading child agents...</div>;
  }
  if (children.error) {
    return (
      <EmptyState
        title="child agents unavailable"
        description="the dashboard could not load synthetic child runs for this algorithm"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[12px] text-muted">
          {rows.length === 1 ? "1 child run" : `${rows.length} child runs`}
        </div>
        <Button size="sm" variant="ghost" onClick={() => setGrouped((current) => !current)}>
          {grouped ? "ungroup" : "group"}
        </Button>
      </div>
      <RunTable
        rows={rows}
        columns={columns}
        storageKey={`algorithm-agents.${runId}`}
        rowHref={(row) => childHref(row)}
        {...(grouped ? { groupBy: groupByAgent } : {})}
        emptyTitle="no child agents"
        emptyDescription="this algorithm has not spawned synthetic child runs yet"
      />
    </div>
  );
}

function childToRow(child: ChildRunSummary): RunRow {
  const hash = child.hash_content ?? child.root_agent_path ?? child.run_id;
  const className = child.algorithm_class ?? child.root_agent_path?.split(".").at(-1) ?? "Agent";
  const totalTokens = child.prompt_tokens + child.completion_tokens;
  return {
    id: child.run_id,
    identity: hash,
    state: child.state,
    startedAt: child.started_at,
    endedAt: child.started_at + child.duration_ms / 1000,
    durationMs: child.duration_ms,
    fields: {
      agent: { kind: "text", value: className, mono: true },
      group: { kind: "text", value: hash, mono: true },
      events: { kind: "num", value: child.event_total, format: "int" },
      tokens: { kind: "num", value: totalTokens, format: "tokens" },
      cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
      score: { kind: "num", value: child.algorithm_terminal_score, format: "score" },
    },
  };
}

function groupByAgent(row: RunRow): { key: string; label: string } {
  const field = row.fields.group;
  const value = field?.kind === "text" ? field.value : row.identity;
  return { key: value, label: truncateMiddle(value, 24) };
}

function childHref(row: RunRow): string {
  return `/agents/${encodeURIComponent(row.identity)}/runs/${encodeURIComponent(row.id)}`;
}
