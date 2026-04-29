import { useMemo } from "react";
import { z } from "zod";

import { EmptyState } from "@/components/ui/empty-state";
import { type RunRow, RunTable, type RunTableColumn } from "@/components/ui/run-table";
import { agentsSummaryLangfuse, parseTopIndices, rankBeamCandidates } from "@/lib/beam-data";
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
  { id: "diff", label: "Diff preview", source: "diff", sortable: true, width: "1fr" },
  { id: "selected", label: "Selected", source: "selected", sortable: true, width: 92 },
  { id: "langfuse", label: "Langfuse", source: "langfuse", width: 84 },
];

interface BeamLeaderboardTabProps {
  data: unknown;
  dataIterations?: unknown;
  dataChildren?: unknown;
  dataAgentsSummary?: unknown;
  runId: string;
}

export function BeamLeaderboardTab({
  data,
  dataIterations,
  dataChildren,
  dataAgentsSummary,
  runId,
}: BeamLeaderboardTabProps) {
  const parsed = CandidateArray.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no candidates" description="beam has not emitted candidates yet" />;
  }

  const children = parseChildren(dataChildren);
  const childrenByCandidate = useMemo(() => mapChildrenByCandidate(children), [children]);
  const topIndices = useMemo(() => parseTopIndices(dataIterations), [dataIterations]);
  const ranked = useMemo(
    () => rankBeamCandidates(parsed.data, topIndices),
    [parsed.data, topIndices],
  );
  const fallbackLangfuse = agentsSummaryLangfuse(dataAgentsSummary);

  const scoreBounds = scoreRange(parsed.data);
  const rows = ranked.map((entry): RunRow => {
    const { candidate, candidateIndex, rank, previousText, selected } = entry;
    const child = childrenByCandidate.get(candidateIndex) ?? null;
    const text = candidate.text ?? "";
    const score = candidate.score;
    const langfuseUrl = child?.langfuse_url ?? fallbackLangfuse;

    return {
      id: `candidate-${candidateIndex}`,
      identity: child?.hash_content ?? `${runId}:${candidateIndex}`,
      state: "ended",
      startedAt: child?.started_at ?? null,
      endedAt:
        child?.started_at != null && child.duration_ms != null
          ? child.started_at + child.duration_ms / 1000
          : null,
      durationMs: child?.duration_ms ?? null,
      fields: {
        rank: { kind: "num", value: rank, format: "int" },
        score: {
          kind: "score",
          value: score,
          min: scoreBounds.min,
          max: scoreBounds.max,
        },
        diff: { kind: "diff", value: text, ...(previousText ? { previous: previousText } : {}) },
        selected: selected
          ? { kind: "pill", value: "✓", tone: "ok" }
          : { kind: "text", value: "-", mono: true },
        langfuse: langfuseUrl
          ? { kind: "link", label: "open", to: langfuseUrl }
          : { kind: "text", value: "-", mono: true },
      },
    };
  });

  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={rows}
        columns={columns}
        storageKey={`beam-leaderboard:${runId}`}
        emptyTitle="no leaderboard"
        emptyDescription="beam leaderboard appears after candidate scores are emitted"
      />
    </div>
  );
}

function parseChildren(data: unknown): ChildRunSummary[] {
  const parsed = z.array(ChildRunSummary).safeParse(data);
  return parsed.success
    ? [...parsed.data].sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0))
    : [];
}

function mapChildrenByCandidate(children: ChildRunSummary[]): Map<number, ChildRunSummary> {
  const out = new Map<number, ChildRunSummary>();
  children.forEach((child, fallbackIndex) => {
    const metadata = recordAt(child, "metadata");
    const algorithmMetadata = recordAt(child, "algorithm_metadata");
    const parentRunMetadata = recordAt(child, "parent_run_metadata");
    const index =
      numberAt(child, "candidate_index") ??
      numberAt(metadata, "candidate_index") ??
      numberAt(algorithmMetadata, "candidate_index") ??
      numberAt(parentRunMetadata, "candidate_index") ??
      fallbackIndex;
    out.set(index, child);
  });
  return out;
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

function recordAt(source: unknown, key: string): Record<string, unknown> | null {
  if (!isRecord(source)) return null;
  const value = source[key];
  return isRecord(value) ? value : null;
}

function numberAt(source: unknown, key: string): number | null {
  if (!isRecord(source)) return null;
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
