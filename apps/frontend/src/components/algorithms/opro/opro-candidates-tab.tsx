import {
  buildOPROSteps,
  childHref,
  shortText,
} from "@/components/algorithms/opro/opro-history-tab";
import { EmptyState, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";

const columns: RunTableColumn[] = [
  { id: "step", label: "Step", source: "step", sortable: true, align: "right", width: 64 },
  { id: "status", label: "Status", source: "status", sortable: true, width: 94 },
  { id: "score", label: "Score", source: "score", sortable: true, align: "right", width: 82 },
  { id: "text", label: "Candidate text preview", source: "text", sortable: true, width: "1fr" },
  { id: "param", label: "Param", source: "param", sortable: true, width: 140 },
  { id: "length", label: "Length", source: "length", sortable: true, align: "right", width: 76 },
  { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 76 },
];

export function OPROCandidatesTab({
  dataIterations,
  dataEvents,
  dataChildren,
  runId,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
  dataChildren?: unknown;
  runId: string;
}) {
  const steps = buildOPROSteps(dataIterations, dataEvents, dataChildren).filter(
    (step) => step.score != null || step.accepted != null,
  );
  const rows = steps.map((step) => {
    const cost = (step.proposerRun?.cost?.cost_usd ?? 0) + (step.evaluatorRun?.cost?.cost_usd ?? 0);
    return {
      id: `${step.stepIndex}`,
      identity: runId,
      state: step.accepted === true ? "ended" : "queued",
      startedAt: step.proposedAt,
      endedAt: step.evaluatedAt,
      durationMs: null,
      fields: {
        step: { kind: "num", value: step.stepIndex, format: "int" },
        status: {
          kind: "pill",
          value: step.accepted === true ? "accepted" : "rejected",
          tone: step.accepted === true ? "ok" : "warn",
        },
        score: { kind: "num", value: step.score, format: "score" },
        text: { kind: "markdown", value: shortText(step.candidateValue, 80) },
        param: { kind: "text", value: step.paramPath, mono: true },
        length: { kind: "num", value: step.candidateValue.length, format: "int" },
        cost: { kind: "num", value: cost > 0 ? cost : null, format: "cost" },
      },
    } satisfies RunRow;
  });

  if (rows.length === 0) {
    return (
      <EmptyState
        title="no candidate evaluations"
        description="OPRO has not emitted evaluate events for candidates yet"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={rows}
        columns={columns}
        storageKey={`opro-candidates:${runId}`}
        rowHref={(row) => {
          const step = steps.find((candidate) => String(candidate.stepIndex) === row.id);
          return step?.evaluatorRun ? childHref(step.evaluatorRun) : null;
        }}
        pageSize={50}
        emptyTitle="no candidates"
        emptyDescription="candidate proposals appear after OPRO evaluate events"
      />
    </div>
  );
}
