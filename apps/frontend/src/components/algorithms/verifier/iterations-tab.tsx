import { EmptyState, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";
import { IterationsResponse } from "@/lib/types";

type IterationRow = IterationsResponse["iterations"][number];

type IterationSummary = {
  iterIndex: number;
  candidateText: string;
  score: number | null;
  accepted: boolean | null;
};

const columns: RunTableColumn[] = [
  {
    id: "iter",
    label: "iter",
    source: "fields.iter",
    width: 64,
    sortable: true,
    defaultSort: "asc",
  },
  {
    id: "candidate_text",
    label: "candidate_text",
    source: "fields.candidate_text",
    width: "1fr",
  },
  {
    id: "verifier_score",
    label: "verifier_score",
    source: "fields.verifier_score",
    width: 180,
    sortable: true,
  },
  {
    id: "accepted",
    label: "accepted",
    source: "fields.accepted",
    width: 120,
    sortable: true,
  },
];

export function VerifierIterationsTab({ data }: { data?: unknown }) {
  const parsed = IterationsResponse.safeParse(data);
  if (!parsed.success) {
    return <EmptyState title="no verifier iterations" description="waiting for iteration events" />;
  }

  const summaries = summarizeIterations(parsed.data.iterations, parsed.data.threshold);
  if (summaries.length === 0) {
    return <EmptyState title="no verifier iterations" description="waiting for iteration events" />;
  }

  const rows = toRunRows(summaries);
  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={rows}
        columns={columns}
        storageKey="algo.verifier.iterations"
        emptyTitle="no verifier iterations"
        emptyDescription="iteration events have not arrived for this verifier run"
      />
    </div>
  );
}

function toRunRows(entries: IterationSummary[]): RunRow[] {
  const scoreValues = entries
    .map((entry) => entry.score)
    .filter((value): value is number => typeof value === "number");
  const min = scoreValues.length > 0 ? Math.min(...scoreValues) : undefined;
  const max = scoreValues.length > 0 ? Math.max(...scoreValues) : undefined;

  let previousText: string | null = null;
  return entries.map((entry) => {
    const deltaFrom = previousText;
    previousText = entry.candidateText;

    const accepted = entry.accepted;
    return {
      id: `iter-${entry.iterIndex}`,
      identity: entry.candidateText.trim() || `iter-${entry.iterIndex}`,
      state: accepted === true ? "ended" : accepted === false ? "queued" : "running",
      startedAt: null,
      endedAt: null,
      durationMs: null,
      fields: {
        iter: { kind: "num", value: entry.iterIndex + 1, format: "int" },
        candidate_text: {
          kind: "diff",
          value: entry.candidateText,
          ...(deltaFrom ? { previous: deltaFrom } : {}),
        },
        verifier_score: {
          kind: "score",
          value: entry.score,
          ...(min != null ? { min } : {}),
          ...(max != null ? { max } : {}),
        },
        accepted: {
          kind: "pill",
          value: accepted === true ? "accepted" : accepted === false ? "rejected" : "unknown",
          tone: accepted === true ? "ok" : accepted === false ? "warn" : "default",
        },
      },
    };
  });
}

function summarizeIterations(rows: IterationRow[], threshold: number | null): IterationSummary[] {
  const byIter = new Map<number, IterationSummary>();

  for (const row of rows) {
    const current = byIter.get(row.iter_index) ?? {
      iterIndex: row.iter_index,
      candidateText: "",
      score: null,
      accepted: null,
    };

    if (typeof row.text === "string" && row.text.trim().length > 0) {
      current.candidateText = row.text;
    }
    if (typeof row.score === "number") {
      current.score = row.score;
    }

    const metadataAccepted =
      row.metadata.accepted === true ? true : row.metadata.accepted === false ? false : null;
    current.accepted = inferAccepted(metadataAccepted, current.score, threshold);

    byIter.set(row.iter_index, current);
  }

  return [...byIter.values()].sort((a, b) => a.iterIndex - b.iterIndex);
}

function inferAccepted(
  metadataAccepted: boolean | null,
  score: number | null,
  threshold: number | null,
): boolean | null {
  if (metadataAccepted != null) return metadataAccepted;
  if (score == null || threshold == null) return null;
  return score >= threshold;
}
