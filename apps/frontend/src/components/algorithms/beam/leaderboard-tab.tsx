import { ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import { z } from "zod";

import { EmptyState } from "@/components/ui/empty-state";
import { type RunRow, RunTable, type RunTableColumn } from "@/components/ui/run-table";
import { Candidate, RunSummary as RunSummarySchema } from "@/lib/types";

const CandidateArray = z.array(Candidate);

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
  langfuse_url: z.string().nullable().optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

const columns: RunTableColumn[] = [
  { id: "rank", label: "Rank", source: "rank", sortable: true, align: "right", width: 64 },
  { id: "score", label: "Score", source: "score", sortable: true, width: 180 },
  { id: "text", label: "Text preview", source: "text", sortable: true, width: "1fr" },
  { id: "selected", label: "Selected", source: "selected", sortable: true, width: 92 },
  { id: "langfuse", label: "Langfuse", source: "langfuse", width: 84 },
];

interface BeamLeaderboardTabProps {
  data: unknown;
  dataIterations?: unknown;
  dataChildren?: unknown;
  runId: string;
}

export function BeamLeaderboardTab({
  data,
  dataIterations,
  dataChildren,
  runId,
}: BeamLeaderboardTabProps) {
  const parsed = CandidateArray.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no candidates" description="beam has not emitted candidates yet" />;
  }

  const children = parseChildren(dataChildren);
  const topIndices = useMemo(() => parseTopIndices(dataIterations), [dataIterations]);
  const sorted = sortCandidates(parsed.data);
  const k = topIndices.size > 0 ? topIndices.size : Math.min(5, sorted.length);
  const topRows = sorted.slice(0, k);
  const [showAll, setShowAll] = useState(false);

  const scoreBounds = scoreRange(sorted);
  const rowFor = (candidate: z.infer<typeof Candidate>, rank: number): RunRow => {
    const candidateIndex = candidate.candidate_index ?? rank;
    const child = children[candidateIndex] ?? null;
    const selected = topIndices.size > 0 ? topIndices.has(candidateIndex) : rank < k;
    const text = candidate.text ?? "";
    const score = candidate.score;

    return {
      id: `candidate-${candidateIndex}`,
      identity: child?.hash_content ?? `${runId}:${candidateIndex}`,
      state: "ended",
      startedAt: child?.started_at ?? null,
      endedAt: child?.started_at != null && child.duration_ms != null
        ? child.started_at + child.duration_ms / 1000
        : null,
      durationMs: child?.duration_ms ?? null,
      fields: {
        rank: { kind: "num", value: rank + 1, format: "int" },
        score: {
          kind: "score",
          value: score,
          min: scoreBounds.min,
          max: scoreBounds.max,
        },
        text: { kind: "diff", value: text },
        selected: selected
          ? { kind: "pill", value: "✓", tone: "ok" }
          : { kind: "text", value: "-", mono: true },
        langfuse: child?.langfuse_url
          ? { kind: "link", label: "→", to: child.langfuse_url }
          : { kind: "text", value: "-", mono: true },
      },
    };
  };

  const topKRows = topRows.map((candidate, rank) => rowFor(candidate, rank));
  const allRows = sorted.map((candidate, rank) => rowFor(candidate, rank));

  return (
    <div className="h-full overflow-auto p-4">
      <div className="sticky top-0 z-10 mb-3 border-b border-border bg-bg pb-2">
        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-bg-2 px-2.5 py-1 text-[11px] font-medium text-text">
          K = {k} of {sorted.length}
        </span>
      </div>

      <RunTable
        rows={topKRows}
        columns={columns}
        storageKey={`beam-leaderboard-topk:${runId}`}
        emptyTitle="no leaderboard"
        emptyDescription="beam leaderboard appears after candidate scores are emitted"
      />

      {showAll ? (
        <div className="mt-3">
          <RunTable
            rows={allRows}
            columns={columns}
            storageKey={`beam-leaderboard-all:${runId}`}
            emptyTitle="no candidates"
            emptyDescription="beam candidates appear after candidate events are emitted"
          />
        </div>
      ) : (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-2 px-2.5 py-1 text-[11px] text-muted transition-colors hover:text-text"
          >
            show all candidates
            <ExternalLink size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

function parseChildren(data: unknown): ChildRunSummary[] {
  const parsed = z.array(ChildRunSummary).safeParse(data);
  return parsed.success
    ? [...parsed.data].sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0))
    : [];
}

function parseTopIndices(data: unknown): Set<number> {
  if (!data || typeof data !== "object" || Array.isArray(data)) return new Set();
  const rows = (data as Record<string, unknown>).iterations;
  if (!Array.isArray(rows)) return new Set();
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    if (!row || typeof row !== "object") continue;
    const metadata = (row as Record<string, unknown>).metadata;
    if (!metadata || typeof metadata !== "object") continue;
    const top = (metadata as Record<string, unknown>).top_indices;
    if (Array.isArray(top)) {
      return new Set(top.filter((value): value is number => typeof value === "number"));
    }
  }
  return new Set();
}

function sortCandidates(candidates: z.infer<typeof Candidate>[]): z.infer<typeof Candidate>[] {
  return [...candidates].sort((a, b) => {
    const scoreA = a.score ?? Number.NEGATIVE_INFINITY;
    const scoreB = b.score ?? Number.NEGATIVE_INFINITY;
    if (scoreA !== scoreB) return scoreB - scoreA;
    return (a.candidate_index ?? 0) - (b.candidate_index ?? 0);
  });
}

function scoreRange(candidates: z.infer<typeof Candidate>[]): { min: number; max: number } {
  const scores = candidates
    .map((candidate) => candidate.score)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));
  if (scores.length === 0) return { min: 0, max: 1 };
  return {
    min: Math.min(...scores),
    max: Math.max(...scores),
  };
}
