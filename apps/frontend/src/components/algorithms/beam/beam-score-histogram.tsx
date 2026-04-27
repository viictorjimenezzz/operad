import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useUrlState } from "@/hooks/use-url-state";
import { Candidate } from "@/lib/types";
import { formatNumber } from "@/lib/utils";
import { z } from "zod";

const CandidateArray = z.array(Candidate);

interface BeamScoreHistogramProps {
  data: unknown;
  dataIterations?: unknown;
}

export function BeamScoreHistogram({ data, dataIterations }: BeamScoreHistogramProps) {
  const parsed = CandidateArray.safeParse(data);
  const [, setScoreFilter] = useUrlState("score");
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no beam candidates" description="waiting for candidate scores" />;
  }

  const hasScores = parsed.data.some((candidate) => candidate.score != null);
  const values = hasScores
    ? parsed.data
        .map((candidate) => candidate.score)
        .filter((score): score is number => typeof score === "number")
    : parsed.data.map((candidate) => (candidate.text ?? "").length);
  const bins = buildBins(values, 8);
  const threshold = topKThreshold(parsed.data, dataIterations);
  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-border bg-bg-1 p-3">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-[13px] font-medium text-text">
              {hasScores ? "score distribution" : "text length distribution"}
            </div>
            <div className="text-[11px] text-muted">
              {hasScores
                ? "click a bin to filter candidates"
                : "judge=None: candidates are unscored"}
            </div>
          </div>
          <Button size="sm" variant="ghost" onClick={() => setScoreFilter(null)}>
            clear filter
          </Button>
        </div>
        <div className="flex h-56 items-end gap-2 border-b border-border px-1 pb-2">
          {bins.map((bin) => (
            <button
              key={`${bin.min}-${bin.max}`}
              type="button"
              onClick={() => hasScores && setScoreFilter(`${bin.min}:${bin.max}`)}
              className="group flex h-full min-w-0 flex-1 flex-col justify-end gap-1 text-left"
              disabled={!hasScores}
            >
              <div
                className="w-full rounded-t bg-[--color-accent] transition-opacity group-hover:opacity-80"
                style={{ height: `${Math.max(4, (bin.count / maxCount) * 100)}%` }}
              />
              <div className="truncate font-mono text-[10px] text-muted-2">
                {formatNumber(bin.min)}
              </div>
            </button>
          ))}
        </div>
        {hasScores && threshold != null ? (
          <div className="mt-2 text-[11px] text-muted">
            top-k threshold:{" "}
            <span className="font-mono text-[--color-ok]">{threshold.toFixed(3)}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function buildBins(
  values: number[],
  count: number,
): Array<{ min: number; max: number; count: number }> {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min || 1) / count;
  const bins = Array.from({ length: count }, (_, index) => ({
    min: min + index * width,
    max: min + (index + 1) * width,
    count: 0,
  }));
  for (const value of values) {
    const index = Math.min(Math.floor((value - min) / width), bins.length - 1);
    const bin = bins[index];
    if (bin) bin.count += 1;
  }
  return bins;
}

function topKThreshold(candidates: Candidate[], iterationsData: unknown): number | null {
  const top = parseTopIndices(iterationsData);
  if (top.size === 0) return null;
  const scores = candidates
    .filter((candidate) => candidate.candidate_index != null && top.has(candidate.candidate_index))
    .map((candidate) => candidate.score)
    .filter((score): score is number => typeof score === "number")
    .sort((a, b) => a - b);
  return scores[0] ?? null;
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
