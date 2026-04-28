import { buildTurnRows } from "@/components/algorithms/talker_reasoner/transcript-tab";
import { EmptyState, RunTable, type RunRow, type RunTableColumn } from "@/components/ui";

interface TalkerDecisionsTabProps {
  runId?: string;
  dataSummary?: unknown;
  dataEvents?: unknown;
}

const columns: RunTableColumn[] = [
  { id: "turn", label: "turn", source: "turn", sortable: true, width: 68 },
  {
    id: "routerChoice",
    label: "router choice",
    source: "routerChoice",
    sortable: true,
    width: 130,
  },
  {
    id: "routerConfidence",
    label: "router confidence",
    source: "routerConfidence",
    sortable: true,
    width: 190,
  },
  {
    id: "finalResponsePreview",
    label: "final response preview",
    source: "finalResponsePreview",
    sortable: false,
    width: "1fr",
  },
  { id: "langfuse", label: "langfuse →", source: "langfuse", sortable: false, width: 120 },
];

export function TalkerDecisionsTab({ runId, dataSummary, dataEvents }: TalkerDecisionsTabProps) {
  const turns = buildTurnRows(dataSummary, dataEvents);
  const confidenceValues = turns
    .map((turn) => turn.routerConfidence)
    .filter((value): value is number => value != null);
  const min = confidenceValues.length > 0 ? Math.min(...confidenceValues) : 0;
  const max = confidenceValues.length > 0 ? Math.max(...confidenceValues) : 1;

  const rows: RunRow[] = turns.map((turn) => ({
    id: String(turn.turn),
    identity: turn.talkerPath || turn.reasonerPath || turn.routerChoice || String(turn.turn),
    state: "ended",
    startedAt: null,
    endedAt: null,
    durationMs: null,
    fields: {
      turn: { kind: "num", value: turn.turn, format: "int" },
      routerChoice: {
        kind: "pill",
        value: turn.routerChoice,
        tone: tone(turn.routerChoice),
      },
      routerConfidence: {
        kind: "score",
        value: turn.routerConfidence,
        min,
        max,
      },
      finalResponsePreview: {
        kind: "diff",
        value: turn.finalResponsePreview || "",
      },
      langfuse: turn.langfuseUrl
        ? { kind: "link", label: "open", to: turn.langfuseUrl }
        : { kind: "text", value: "-" },
    },
  }));

  if (rows.length === 0) {
    return (
      <EmptyState
        title="no decisions yet"
        description="TalkerReasoner speak events will populate this table"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={rows}
        columns={columns}
        storageKey={`talker-decisions.${runId ?? "run"}`}
        rowHref={(row) =>
          runId ? `/algorithms/${encodeURIComponent(runId)}?tab=transcript&turn=${row.id}` : null
        }
        emptyTitle="no decisions"
        emptyDescription="TalkerReasoner has not emitted navigation decisions"
      />
    </div>
  );
}

function tone(choice: string): "ok" | "warn" | "error" | "accent" | "default" {
  const normalized = choice.toLowerCase();
  if (normalized.includes("talk") || normalized === "advance") return "accent";
  if (normalized.includes("reason") || normalized === "branch") return "ok";
  if (normalized === "finish") return "warn";
  return "default";
}
