import {
  asRecord,
  decisionTone,
  extractTalkerTurns,
  numberValue,
  stringValue,
} from "@/components/algorithms/talker_reasoner/transcript-view";
import { EmptyState, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";

interface DecisionsViewProps {
  runId: string;
  summary?: unknown;
  events?: unknown;
  childRuns?: unknown;
}

interface ChildSummary {
  runId: string;
  path: string;
  startedAt: number | null;
  durationMs: number | null;
  costUsd: number | null;
}

const columns: RunTableColumn[] = [
  { id: "turn", label: "Turn", source: "turn", sortable: true, width: 68 },
  { id: "from", label: "From node", source: "from", sortable: true, width: "1fr" },
  { id: "decision", label: "Decision", source: "decision", sortable: true, width: 110 },
  { id: "to", label: "To node", source: "to", sortable: true, width: "1fr" },
  { id: "latency", label: "Latency", source: "latency", sortable: true, align: "right", width: 86 },
  {
    id: "reasonerCost",
    label: "Reasoner cost",
    source: "reasonerCost",
    sortable: true,
    align: "right",
    width: 112,
  },
  {
    id: "assistantCost",
    label: "Assistant cost",
    source: "assistantCost",
    sortable: true,
    align: "right",
    width: 116,
  },
  { id: "total", label: "Total", source: "total", sortable: true, align: "right", width: 78 },
];

export function DecisionsView({ runId, summary, events, childRuns }: DecisionsViewProps) {
  const turns = extractTalkerTurns(summary, events);
  const childPairs = pairChildrenByTurn(childRuns);
  const rows = turns.map((turn, index): RunRow => {
    const pair = childPairs[index] ?? { reasoner: null, assistant: null };
    const reasonerCost = pair.reasoner?.costUsd ?? null;
    const assistantCost = pair.assistant?.costUsd ?? null;
    const totalCost = (reasonerCost ?? 0) + (assistantCost ?? 0);
    const latency = (pair.reasoner?.durationMs ?? 0) + (pair.assistant?.durationMs ?? 0) || null;
    return {
      id: String(turn.turnIndex + 1),
      identity: turn.decisionKind || turn.toNodeId || String(turn.turnIndex),
      state: "ended",
      startedAt: pair.reasoner?.startedAt ?? pair.assistant?.startedAt ?? null,
      endedAt: null,
      durationMs: latency,
      fields: {
        turn: { kind: "num", value: turn.turnIndex + 1, format: "int" },
        from: { kind: "text", value: turn.fromNodeId || "-", mono: true },
        decision: {
          kind: "pill",
          value: turn.decisionKind,
          tone: decisionTone(turn.decisionKind),
        },
        to: { kind: "text", value: turn.toNodeId || "-", mono: true },
        latency: { kind: "num", value: latency, format: "ms" },
        reasonerCost: { kind: "num", value: reasonerCost, format: "cost" },
        assistantCost: { kind: "num", value: assistantCost, format: "cost" },
        total: { kind: "num", value: totalCost > 0 ? totalCost : null, format: "cost" },
      },
    };
  });

  if (rows.length === 0) {
    return (
      <EmptyState
        title="no navigation decisions yet"
        description="TalkerReasoner speak events will populate this table"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={rows}
        columns={columns}
        storageKey={`talker-decisions.${runId}`}
        rowHref={(row) => `/algorithms/${encodeURIComponent(runId)}?tab=transcript&turn=${row.id}`}
        emptyTitle="no decisions"
        emptyDescription="TalkerReasoner has not emitted navigation decisions"
      />
    </div>
  );
}

function pairChildrenByTurn(children: unknown): Array<{
  reasoner: ChildSummary | null;
  assistant: ChildSummary | null;
}> {
  const reasoners: ChildSummary[] = [];
  const assistants: ChildSummary[] = [];
  for (const item of Array.isArray(children) ? children : []) {
    const child = childSummary(item);
    if (!child) continue;
    if (isAssistant(child.path)) assistants.push(child);
    else if (isReasoner(child.path)) reasoners.push(child);
  }
  reasoners.sort(compareStarted);
  assistants.sort(compareStarted);
  const length = Math.max(reasoners.length, assistants.length);
  return Array.from({ length }, (_, index) => ({
    reasoner: reasoners[index] ?? null,
    assistant: assistants[index] ?? null,
  }));
}

function childSummary(item: unknown): ChildSummary | null {
  const record = asRecord(item);
  const runId = stringValue(record?.run_id);
  if (!runId) return null;
  const cost = asRecord(record?.cost);
  return {
    runId,
    path: stringValue(record?.root_agent_path) ?? stringValue(record?.algorithm_class) ?? runId,
    startedAt: numberValue(record?.started_at),
    durationMs: numberValue(record?.duration_ms),
    costUsd: numberValue(cost?.cost_usd),
  };
}

function isAssistant(path: string): boolean {
  return path.includes("Assistant") || path.includes("Talker");
}

function isReasoner(path: string): boolean {
  return path.includes("Navigator") || path.includes("Reasoner");
}

function compareStarted(a: ChildSummary, b: ChildSummary): number {
  return (a.startedAt ?? 0) - (b.startedAt ?? 0);
}
