import { EmptyState } from "@/components/ui/empty-state";
import { IterationsResponse } from "@/lib/types";

type IterationRow = IterationsResponse["iterations"][number];

type IterationSummary = {
  iterIndex: number;
  score: number | null;
  accepted: boolean | null;
};

const HISTOGRAM_WIDTH = 560;
const HISTOGRAM_HEIGHT = 180;
const HISTOGRAM_PAD_X = 24;
const HISTOGRAM_PAD_Y = 20;

const TREND_WIDTH = 560;
const TREND_HEIGHT = 120;
const TREND_PAD_X = 20;
const TREND_PAD_Y = 16;

export function VerifierAcceptanceTab({ data }: { data?: unknown }) {
  const parsed = IterationsResponse.safeParse(data);
  if (!parsed.success) {
    return <EmptyState title="no acceptance data" description="waiting for verifier iterations" />;
  }

  const entries = summarizeIterations(parsed.data.iterations, parsed.data.threshold);
  if (entries.length === 0) {
    return <EmptyState title="no acceptance data" description="waiting for verifier iterations" />;
  }

  const acceptedCount = entries.filter((entry) => entry.accepted === true).length;
  const rejectedCount = entries.filter((entry) => entry.accepted === false).length;
  const scores = entries
    .map((entry) => entry.score)
    .filter((score): score is number => typeof score === "number");

  const threshold = parsed.data.threshold;
  const domainMin = Math.min(...scores, threshold ?? 0);
  const domainMax = Math.max(...scores, threshold ?? 1);
  const domainSpan = Math.max(domainMax - domainMin, 1e-9);

  const plotWidth = HISTOGRAM_WIDTH - HISTOGRAM_PAD_X * 2;
  const plotHeight = HISTOGRAM_HEIGHT - HISTOGRAM_PAD_Y * 2;
  const x0 = HISTOGRAM_PAD_X;
  const x1 = x0 + plotWidth;
  const thresholdX =
    threshold == null ? null : x0 + ((threshold - domainMin) / domainSpan) * plotWidth;

  const maxCount = Math.max(1, acceptedCount, rejectedCount);
  const rejectedHeight = (rejectedCount / maxCount) * plotHeight;
  const acceptedHeight = (acceptedCount / maxCount) * plotHeight;

  const trend = buildCumulativeTrend(entries);
  const trendRate = trend.length > 0 ? trend[trend.length - 1]?.rate ?? 0 : 0;

  return (
    <div className="h-full overflow-auto p-4">
      <div className="flex flex-col gap-4">
        <section className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="m-0 text-[13px] font-medium text-text">Acceptance split</h3>
            <div className="text-[11px] text-muted">
              accepted <span className="font-mono text-[--color-ok]">{acceptedCount}</span> · rejected{" "}
              <span className="font-mono text-[--color-warn]">{rejectedCount}</span>
            </div>
          </div>

          <svg viewBox={`0 0 ${HISTOGRAM_WIDTH} ${HISTOGRAM_HEIGHT}`} className="h-44 w-full">
            <rect
              x={x0}
              y={HISTOGRAM_PAD_Y + (plotHeight - rejectedHeight)}
              width={Math.max(0, (thresholdX ?? x1) - x0)}
              height={rejectedHeight}
              fill="var(--color-warn-dim)"
            />
            <rect
              x={thresholdX ?? x0}
              y={HISTOGRAM_PAD_Y + (plotHeight - acceptedHeight)}
              width={Math.max(0, x1 - (thresholdX ?? x0))}
              height={acceptedHeight}
              fill="var(--color-ok-dim)"
            />

            {thresholdX != null ? (
              <line
                aria-label="threshold line"
                x1={thresholdX}
                x2={thresholdX}
                y1={HISTOGRAM_PAD_Y - 2}
                y2={HISTOGRAM_PAD_Y + plotHeight + 2}
                stroke="var(--color-accent)"
                strokeWidth="1.5"
                strokeDasharray="3 2"
              />
            ) : null}

            <line
              x1={x0}
              x2={x1}
              y1={HISTOGRAM_PAD_Y + plotHeight}
              y2={HISTOGRAM_PAD_Y + plotHeight}
              stroke="var(--color-border)"
            />

            <text x={x0} y={HISTOGRAM_HEIGHT - 6} className="fill-[var(--color-muted)] text-[11px]">
              rejected
            </text>
            <text
              x={x1}
              y={HISTOGRAM_HEIGHT - 6}
              textAnchor="end"
              className="fill-[var(--color-muted)] text-[11px]"
            >
              accepted
            </text>
            {threshold != null ? (
              <text
                x={Math.min(Math.max(thresholdX ?? x0, x0 + 36), x1 - 36)}
                y={12}
                textAnchor="middle"
                className="fill-[var(--color-accent)] text-[11px]"
              >
                threshold {threshold.toFixed(2)}
              </text>
            ) : null}
          </svg>
        </section>

        <section className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="m-0 text-[13px] font-medium text-text">Acceptance rate over iterations</h3>
            <div className="font-mono text-[11px] text-muted">{(trendRate * 100).toFixed(1)}%</div>
          </div>

          {trend.length > 0 ? (
            <svg viewBox={`0 0 ${TREND_WIDTH} ${TREND_HEIGHT}`} className="h-24 w-full">
              <line
                x1={TREND_PAD_X}
                x2={TREND_WIDTH - TREND_PAD_X}
                y1={TREND_HEIGHT - TREND_PAD_Y}
                y2={TREND_HEIGHT - TREND_PAD_Y}
                stroke="var(--color-border)"
              />
              <polyline
                aria-label="acceptance rate line"
                fill="none"
                stroke="var(--color-accent)"
                strokeWidth="2"
                points={trendPolylinePoints(trend)}
              />
            </svg>
          ) : (
            <div className="rounded border border-border bg-bg-2 px-2 py-2 text-[11px] text-muted">
              acceptance rate is unavailable because no iterations include a verdict yet
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function summarizeIterations(rows: IterationRow[], threshold: number | null): IterationSummary[] {
  const byIter = new Map<number, IterationSummary>();

  for (const row of rows) {
    const current = byIter.get(row.iter_index) ?? {
      iterIndex: row.iter_index,
      score: null,
      accepted: null,
    };

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

function buildCumulativeTrend(entries: IterationSummary[]): Array<{ index: number; rate: number }> {
  const trend: Array<{ index: number; rate: number }> = [];
  let seen = 0;
  let accepted = 0;

  for (const entry of entries) {
    if (entry.accepted == null) continue;
    seen += 1;
    if (entry.accepted) accepted += 1;
    trend.push({ index: entry.iterIndex, rate: accepted / seen });
  }

  return trend;
}

function trendPolylinePoints(trend: Array<{ index: number; rate: number }>): string {
  if (trend.length === 1) {
    const x = TREND_PAD_X;
    const y = TREND_PAD_Y + (1 - trend[0].rate) * (TREND_HEIGHT - TREND_PAD_Y * 2);
    return `${x},${y} ${TREND_WIDTH - TREND_PAD_X},${y}`;
  }

  const innerWidth = TREND_WIDTH - TREND_PAD_X * 2;
  const innerHeight = TREND_HEIGHT - TREND_PAD_Y * 2;

  return trend
    .map((point, idx) => {
      const x = TREND_PAD_X + (idx / Math.max(1, trend.length - 1)) * innerWidth;
      const y = TREND_PAD_Y + (1 - point.rate) * innerHeight;
      return `${x},${y}`;
    })
    .join(" ");
}
