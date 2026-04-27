import {
  type ChildRunSummary,
  CriticRationaleCard,
} from "@/components/algorithms/beam/critic-rationale-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { Candidate, RunSummary as RunSummarySchema } from "@/lib/types";
import { cn, formatCost, formatDurationMs } from "@/lib/utils";
import { ExternalLink, Star } from "lucide-react";
import { useMemo, useState } from "react";
import { z } from "zod";

const CandidateArray = z.array(Candidate);
const ChildrenArray = z.array(
  RunSummarySchema.passthrough().extend({
    hash_content: z.string().nullable().optional(),
  }),
);

interface BeamLeaderboardProps {
  data: unknown;
  dataIterations?: unknown;
  dataChildren?: unknown;
  runId: string;
}

export function BeamLeaderboard({ data, dataIterations, dataChildren }: BeamLeaderboardProps) {
  const parsed = CandidateArray.safeParse(data);
  const children = parseChildren(dataChildren);
  const topIndices = useMemo(() => parseTopIndices(dataIterations), [dataIterations]);
  const scoreRange = parseScoreRange();
  const [expanded, setExpanded] = useState<number | null>(null);

  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no candidates" description="beam has not emitted candidates yet" />;
  }
  const firstCandidate = parsed.data[0];
  if (!firstCandidate) {
    return <EmptyState title="no candidates" description="beam has not emitted candidates yet" />;
  }

  const pairings = pairChildren(children);
  const hasScores = parsed.data.some((candidate) => candidate.score != null);
  const rows = [...parsed.data]
    .filter((candidate) => scoreRangeAllows(candidate.score, scoreRange))
    .sort((a, b) => {
      if (!hasScores) return (a.candidate_index ?? 0) - (b.candidate_index ?? 0);
      return (b.score ?? Number.NEGATIVE_INFINITY) - (a.score ?? Number.NEGATIVE_INFINITY);
    });
  const maxScore = Math.max(0, ...rows.map((row) => row.score ?? 0));

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-lg border border-border bg-bg-1">
        <table className="w-full table-fixed text-[12px]">
          <thead className="bg-bg-2 text-[10px] uppercase tracking-[0.06em] text-muted-2">
            <tr>
              <th className="w-12 px-2 py-2 text-left font-medium">Rank</th>
              <th className="w-24 px-2 py-2 text-left font-medium">Candidate</th>
              {hasScores ? <th className="w-28 px-2 py-2 text-left font-medium">Score</th> : null}
              <th className="px-2 py-2 text-left font-medium">Text preview</th>
              <th className="w-32 px-2 py-2 text-right font-medium">Cost</th>
              <th className="w-28 px-2 py-2 text-right font-medium">Latency</th>
              <th className="w-20 px-2 py-2 text-right font-medium">Run</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((candidate, index) => {
              const candidateIndex = candidate.candidate_index ?? index;
              const pairing = pairings.get(candidateIndex);
              const isTop = topIndices.has(candidateIndex);
              const generatorHref = pairing?.generator ? childHref(pairing.generator) : null;
              return (
                <tr
                  key={candidateIndex}
                  className={cn(
                    "cursor-pointer border-b border-border/70 last:border-b-0 hover:bg-bg-2/60",
                    expanded === candidateIndex && "bg-bg-2/70",
                  )}
                  onClick={() =>
                    setExpanded((current) => (current === candidateIndex ? null : candidateIndex))
                  }
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" && event.key !== " ") return;
                    event.preventDefault();
                    setExpanded((current) => (current === candidateIndex ? null : candidateIndex));
                  }}
                  tabIndex={0}
                >
                  <td className="px-2 py-2 font-mono text-text">
                    <span className="inline-flex items-center gap-1">
                      {isTop ? (
                        <Star size={12} className="fill-[--color-warn] text-[--color-warn]" />
                      ) : null}
                      {hasScores ? index + 1 : "-"}
                    </span>
                  </td>
                  <td className="px-2 py-2 font-mono text-muted">#{candidateIndex}</td>
                  {hasScores ? (
                    <td className="px-2 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 flex-1 rounded bg-bg-3">
                          <div
                            className="h-1.5 rounded bg-[--color-accent]"
                            style={{
                              width: `${maxScore > 0 ? ((candidate.score ?? 0) / maxScore) * 100 : 0}%`,
                            }}
                          />
                        </div>
                        <span className="w-12 text-right font-mono tabular-nums text-text">
                          {candidate.score != null ? candidate.score.toFixed(3) : "-"}
                        </span>
                      </div>
                    </td>
                  ) : null}
                  <td className="px-2 py-2">
                    <div className="line-clamp-2 text-text">
                      <MarkdownView value={truncate(candidate.text ?? "", 120)} />
                    </div>
                  </td>
                  <td className="px-2 py-2 text-right font-mono">
                    {formatCost(pairing?.generator?.cost?.cost_usd ?? null)}
                  </td>
                  <td className="px-2 py-2 text-right font-mono">
                    {formatDurationMs(pairing?.generator?.duration_ms ?? null)}
                  </td>
                  <td className="px-2 py-2 text-right">
                    {generatorHref ? (
                      <a
                        href={generatorHref}
                        onClick={(event) => event.stopPropagation()}
                        className="inline-flex items-center justify-end text-accent hover:text-[--color-accent-strong]"
                      >
                        <ExternalLink size={14} />
                      </a>
                    ) : (
                      <span className="text-muted-2">-</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {expanded != null ? (
        <CriticRationaleCard
          candidate={
            rows.find((candidate) => candidate.candidate_index === expanded) ?? firstCandidate
          }
          generatorRun={pairings.get(expanded)?.generator ?? null}
          criticRun={pairings.get(expanded)?.critic ?? null}
          rank={rows.findIndex((candidate) => candidate.candidate_index === expanded) + 1}
          topK={topIndices.has(expanded)}
        />
      ) : rows.length > 0 ? (
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setExpanded(rows[0]?.candidate_index ?? null)}
          >
            expand top candidate
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function parseChildren(data: unknown): ChildRunSummary[] {
  const parsed = ChildrenArray.safeParse(data);
  return parsed.success
    ? [...parsed.data].sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0))
    : [];
}

function parseTopIndices(data: unknown): Set<number> {
  if (!data || typeof data !== "object" || Array.isArray(data)) return new Set();
  const rows = (data as Record<string, unknown>).iterations;
  if (!Array.isArray(rows)) return new Set();
  for (const row of rows) {
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

function parseScoreRange(): [number, number] | null {
  if (typeof window === "undefined") return null;
  const raw = new URLSearchParams(window.location.search).get("score");
  if (!raw) return null;
  const [min, max] = raw.split(":").map(Number);
  return Number.isFinite(min) && Number.isFinite(max) ? [min ?? 0, max ?? 0] : null;
}

function scoreRangeAllows(score: number | null, range: [number, number] | null): boolean {
  if (!range || score == null) return true;
  return score >= range[0] && score <= range[1];
}

function pairChildren(
  children: ChildRunSummary[],
): Map<number, { generator?: ChildRunSummary; critic?: ChildRunSummary }> {
  const critics = children.filter((child) => isCritic(child));
  const generators = children.filter((child) => !isCritic(child));
  const out = new Map<number, { generator?: ChildRunSummary; critic?: ChildRunSummary }>();
  const count = Math.max(generators.length, critics.length);
  for (let i = 0; i < count; i += 1) {
    out.set(i, {
      ...(generators[i] ? { generator: generators[i] } : {}),
      ...(critics[i] ? { critic: critics[i] } : {}),
    });
  }
  return out;
}

function isCritic(child: ChildRunSummary): boolean {
  const path = `${child.root_agent_path ?? ""} ${child.algorithm_class ?? ""}`.toLowerCase();
  return path.includes("critic") || path.includes("judge") || path.includes("score");
}

function childHref(child: ChildRunSummary): string {
  const identity = child.hash_content ?? child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 3)}...`;
}
