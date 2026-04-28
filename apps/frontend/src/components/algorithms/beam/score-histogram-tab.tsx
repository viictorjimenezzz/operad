import { EmptyState } from "@/components/ui/empty-state";
import { paletteIndex } from "@/lib/hash-color";
import { Candidate } from "@/lib/types";
import { z } from "zod";

const CandidateArray = z.array(Candidate);

interface BeamScoreHistogramTabProps {
  data: unknown;
  dataIterations?: unknown;
  bins?: number;
}

export function BeamScoreHistogramTab({
  data,
  dataIterations,
  bins = 10,
}: BeamScoreHistogramTabProps) {
  const parsed = CandidateArray.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no beam candidates" description="waiting for candidate scores" />;
  }

  const scored = parsed.data
    .map((candidate) => candidate.score)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));

  if (scored.length === 0) {
    return (
      <EmptyState
        title="no scored candidates"
        description="beam candidates are present but score values have not been emitted"
      />
    );
  }

  const histogram = buildHistogram(scored, Math.max(1, bins));
  const topIndices = parseTopIndices(dataIterations);
  const cutoff = topKCutoff(parsed.data, topIndices);
  const maxCount = Math.max(1, ...histogram.map((bin) => bin.count));
  const barColor = `var(--qual-${paletteIndex("Beam") + 1})`;
  const lineLeft = cutoff != null ? cutoffLinePosition(cutoff, histogram[0]?.min ?? 0, histogram.at(-1)?.max ?? 1) : null;

  return (
    <div className="h-full overflow-auto p-4">
      <div className="rounded-lg border border-border bg-bg-1 p-3">
        <div className="mb-2 text-[11px] text-muted">{histogram.length} bins</div>
        <div className="relative h-56 border-b border-border px-1 pb-1">
          {lineLeft != null ? (
            <div
              className="pointer-events-none absolute bottom-1 top-0 w-px bg-[--color-warn]"
              style={{ left: `calc(${lineLeft}% + 4px)` }}
              aria-label="k cutoff line"
            />
          ) : null}
          <div className="flex h-full items-end gap-2">
            {histogram.map((bin) => (
              <div key={`${bin.min}-${bin.max}`} className="flex min-w-0 flex-1 flex-col justify-end gap-1">
                <div
                  className="w-full rounded-t"
                  style={{
                    height: `${Math.max(4, (bin.count / maxCount) * 100)}%`,
                    background: barColor,
                  }}
                />
                <div className="truncate font-mono text-[10px] text-muted-2">{bin.min.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </div>
        {cutoff != null ? (
          <div className="mt-2 text-[11px] text-muted">
            K cutoff <span className="font-mono text-[--color-warn]">{cutoff.toFixed(3)}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

type HistogramBin = {
  min: number;
  max: number;
  count: number;
};

function buildHistogram(values: number[], binCount: number): HistogramBin[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  if (span === 0) {
    return Array.from({ length: binCount }, (_, index) => ({
      min: min + index,
      max: min + index + 1,
      count: index === 0 ? values.length : 0,
    }));
  }

  const width = span / binCount;
  const bins = Array.from({ length: binCount }, (_, index) => ({
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

function topKCutoff(candidates: z.infer<typeof Candidate>[], topIndices: Set<number>): number | null {
  if (topIndices.size === 0) return null;
  const scores = candidates
    .filter((candidate) => candidate.candidate_index != null && topIndices.has(candidate.candidate_index))
    .map((candidate) => candidate.score)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));

  if (scores.length === 0) return null;
  return Math.min(...scores);
}

function cutoffLinePosition(value: number, min: number, max: number): number {
  const span = max - min;
  if (span <= 0) return 0;
  return Math.max(0, Math.min(100, ((value - min) / span) * 100));
}
