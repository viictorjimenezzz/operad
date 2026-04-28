import { MultiSeriesChart } from "@/components/ui/multi-series-chart";
import { hashColor } from "@/lib/hash-color";
import type { ReactNode } from "react";

export interface MetricSeriesChartProps {
  points: { x: number; y: number | null; runId: string }[];
  /** Stable identity used to resolve line color consistently via hashColor. */
  identity: string;
  height?: number;
  formatY?: ((n: number) => string) | undefined;
  formatX?: ((n: number) => string) | undefined;
  reference?: { y: number; label: string } | undefined;
  highlightX?: number | undefined;
  yLabel?: ReactNode | undefined;
  xLabel?: ReactNode | undefined;
}

export function MetricSeriesChart({
  points,
  identity,
  height = 200,
  formatY,
  formatX,
  reference,
  highlightX,
  yLabel,
  xLabel,
}: MetricSeriesChartProps) {
  const seriesPoints = points.map((point) => ({ x: point.x, y: point.y }));
  const xs = seriesPoints.map((point) => point.x).filter(Number.isFinite);
  const referenceSeries =
    reference && xs.length > 0
      ? [
          {
            id: `${identity}:reference`,
            label: reference.label,
            points: [
              { x: Math.min(...xs), y: reference.y },
              { x: Math.max(...xs), y: reference.y },
            ],
          },
        ]
      : [];
  const highlightPoint =
    highlightX != null
      ? (points.find((point) => point.x === highlightX && point.y != null) ?? null)
      : null;

  return (
    <div className="relative">
      <MultiSeriesChart
        series={[
          { id: identity, label: identity, points: seriesPoints },
          ...referenceSeries,
          ...(highlightPoint
            ? [{ id: `${identity}:highlight`, label: "selected", points: [highlightPoint] }]
            : []),
        ]}
        height={height}
        {...(formatY ? { formatY } : {})}
        {...(formatX ? { formatX } : {})}
        {...(yLabel != null ? { yLabel } : {})}
        {...(xLabel != null ? { xLabel } : {})}
      />
      {reference ? (
        <div className="pointer-events-none absolute right-2 top-2 rounded bg-bg-1/80 px-1.5 py-0.5 text-[10px] text-muted-2">
          {reference.label}
        </div>
      ) : null}
      {highlightPoint ? (
        <div
          className="pointer-events-none absolute bottom-2 left-2 h-2 w-2 rounded-full"
          style={{ background: hashColor(identity) }}
        />
      ) : null}
    </div>
  );
}
