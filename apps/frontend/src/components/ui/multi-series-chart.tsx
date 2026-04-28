import { hashColor } from "@/lib/hash-color";
import { cn } from "@/lib/utils";
import { type ReactNode, useMemo, useState } from "react";

/**
 * A small, dependency-free multi-series line chart.
 *
 * Each series is identified by a stable string `id` (typically a
 * `run_id` or `hash_content`); the line color is derived from the id
 * via the curated palette so the same identity stays the same color
 * across every panel in the dashboard.
 *
 * Designed for canvas panels that need to show ~1–24 series over time
 * (or over an index axis). Not a replacement for a heavy charting lib;
 * intentionally minimal so it composes inside dense W&B-style grids.
 */

export interface MultiSeriesPoint {
  x: number;
  y: number | null;
}

export interface MultiSeries {
  id: string;
  label?: string;
  /**
   * Optional explicit color for this series.
   * When omitted, the chart resolves color from `hashColor(id)` so identity is stable.
   */
  color?: string;
  points: MultiSeriesPoint[];
}

export interface MultiSeriesChartProps {
  series: MultiSeries[];
  height?: number;
  /** Format function for tooltip y values; defaults to .3 precision. */
  formatY?: (n: number) => string;
  /** Format function for tooltip x values; defaults to integer. */
  formatX?: (n: number) => string;
  /** Render gridlines (default true). */
  grid?: boolean;
  /** Stretch the chart to fill its container width. Default true. */
  fluid?: boolean;
  /** Y-axis label rendered top-left of the plot. */
  yLabel?: ReactNode;
  /** X-axis label rendered bottom-right. */
  xLabel?: ReactNode;
  /** Optional clamp on Y axis. */
  yMin?: number;
  yMax?: number;
  className?: string;
}

const DEFAULT_HEIGHT = 200;
const PADDING = { top: 16, right: 14, bottom: 22, left: 40 };

export function MultiSeriesChart({
  series,
  height = DEFAULT_HEIGHT,
  formatY = (n) => n.toFixed(Math.abs(n) < 1 ? 3 : 2),
  formatX = (n) => Math.round(n).toString(),
  grid = true,
  fluid = true,
  yLabel,
  xLabel,
  yMin,
  yMax,
  className,
}: MultiSeriesChartProps) {
  const [hoverX, setHoverX] = useState<number | null>(null);
  const [containerWidth, setContainerWidth] = useState(640);

  const stats = useMemo(() => {
    const xs: number[] = [];
    const ys: number[] = [];
    for (const s of series) {
      for (const p of s.points) {
        if (Number.isFinite(p.x)) xs.push(p.x);
        if (p.y != null && Number.isFinite(p.y)) ys.push(p.y);
      }
    }
    if (xs.length === 0 || ys.length === 0) return null;
    return {
      xMin: Math.min(...xs),
      xMax: Math.max(...xs),
      yMin: yMin ?? Math.min(...ys),
      yMax: yMax ?? Math.max(...ys),
    };
  }, [series, yMin, yMax]);

  const width = containerWidth;
  const innerW = Math.max(width - PADDING.left - PADDING.right, 1);
  const innerH = Math.max(height - PADDING.top - PADDING.bottom, 1);

  if (!stats) {
    return (
      <div
        className={cn(
          "flex w-full items-center justify-center text-[11px] text-muted-2",
          className,
        )}
        style={{ height }}
      >
        no data
      </div>
    );
  }

  const xSpan = Math.max(stats.xMax - stats.xMin, 1e-9);
  const ySpan = Math.max(stats.yMax - stats.yMin, 1e-9);

  const xToPx = (x: number) => PADDING.left + ((x - stats.xMin) / xSpan) * innerW;
  const yToPx = (y: number) => PADDING.top + (1 - (y - stats.yMin) / ySpan) * innerH;

  const yTicks = niceTicks(stats.yMin, stats.yMax, 4);
  const xTicks = niceTicks(stats.xMin, stats.xMax, 5);

  const onMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    if (px < PADDING.left || px > PADDING.left + innerW) {
      setHoverX(null);
      return;
    }
    const xVal = stats.xMin + ((px - PADDING.left) / innerW) * xSpan;
    setHoverX(xVal);
  };

  const closestPoints = useMemo(() => {
    if (hoverX == null) return [];
    return series
      .map((s) => {
        let nearest: MultiSeriesPoint | null = null;
        let bestDx = Number.POSITIVE_INFINITY;
        for (const p of s.points) {
          if (p.y == null || !Number.isFinite(p.x)) continue;
          const dx = Math.abs(p.x - hoverX);
          if (dx < bestDx) {
            nearest = p;
            bestDx = dx;
          }
        }
        return nearest != null
          ? { id: s.id, label: s.label ?? s.id, point: nearest, color: s.color ?? hashColor(s.id) }
          : null;
      })
      .filter(
        (x): x is { id: string; label: string; point: MultiSeriesPoint; color: string } =>
          x != null,
      )
      .sort((a, b) => (b.point.y ?? 0) - (a.point.y ?? 0));
  }, [hoverX, series]);

  return (
    <div
      ref={(el) => {
        if (el && fluid) setContainerWidth(el.clientWidth || 640);
      }}
      className={cn("relative w-full select-none", className)}
      style={{ height }}
    >
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        onMouseMove={onMouseMove}
        onMouseLeave={() => setHoverX(null)}
        role="img"
        aria-label="multi-series line chart"
      >
        <title>multi-series chart</title>
        {/* Y-axis gridlines + labels */}
        {grid
          ? yTicks.map((t) => (
              <g key={`y-${t}`}>
                <line
                  x1={PADDING.left}
                  x2={width - PADDING.right}
                  y1={yToPx(t)}
                  y2={yToPx(t)}
                  stroke="var(--color-border)"
                  strokeDasharray="2 3"
                  strokeWidth={1}
                  opacity={0.55}
                />
                <text
                  x={PADDING.left - 6}
                  y={yToPx(t)}
                  fontSize={10}
                  fill="var(--color-muted-2)"
                  textAnchor="end"
                  dominantBaseline="central"
                >
                  {formatY(t)}
                </text>
              </g>
            ))
          : null}
        {/* X-axis labels */}
        {grid
          ? xTicks.map((t) => (
              <text
                key={`x-${t}`}
                x={xToPx(t)}
                y={height - 6}
                fontSize={10}
                fill="var(--color-muted-2)"
                textAnchor="middle"
              >
                {formatX(t)}
              </text>
            ))
          : null}
        {/* Plot frame baseline */}
        <line
          x1={PADDING.left}
          x2={width - PADDING.right}
          y1={height - PADDING.bottom}
          y2={height - PADDING.bottom}
          stroke="var(--color-border)"
          strokeWidth={1}
        />
        {/* Series */}
        {series.map((s) => {
          const color = s.color ?? hashColor(s.id);
          const pts = s.points
            .filter((p) => p.y != null && Number.isFinite(p.x))
            .sort((a, b) => a.x - b.x);
          if (pts.length === 0) return null;
          const path = pts
            .map(
              (p, i) =>
                `${i === 0 ? "M" : "L"} ${xToPx(p.x).toFixed(2)} ${yToPx(p.y as number).toFixed(2)}`,
            )
            .join(" ");
          const onlyPoint = pts[0];
          return (
            <g key={s.id}>
              {pts.length === 1 && onlyPoint ? (
                <circle
                  cx={xToPx(onlyPoint.x).toFixed(2)}
                  cy={yToPx(onlyPoint.y as number).toFixed(2)}
                  r={2.5}
                  fill={color}
                  opacity={0.92}
                />
              ) : (
                <path
                  d={path}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={hoverX == null ? 0.92 : 0.8}
                />
              )}
            </g>
          );
        })}
        {/* Hover line + dots */}
        {hoverX != null ? (
          <>
            <line
              x1={xToPx(hoverX)}
              x2={xToPx(hoverX)}
              y1={PADDING.top}
              y2={height - PADDING.bottom}
              stroke="var(--color-border-strong)"
              strokeWidth={1}
            />
            {closestPoints.map((cp) => (
              <circle
                key={cp.id}
                cx={xToPx(cp.point.x)}
                cy={yToPx(cp.point.y as number)}
                r={3}
                fill={cp.color}
                stroke="var(--color-bg-1)"
                strokeWidth={1.5}
              />
            ))}
          </>
        ) : null}
      </svg>
      {yLabel != null ? (
        <span className="pointer-events-none absolute left-2 top-1 text-[10px] uppercase tracking-[0.06em] text-muted-2">
          {yLabel}
        </span>
      ) : null}
      {xLabel != null ? (
        <span className="pointer-events-none absolute bottom-1 right-2 text-[10px] uppercase tracking-[0.06em] text-muted-2">
          {xLabel}
        </span>
      ) : null}
      {hoverX != null && closestPoints.length > 0 ? (
        <div
          className="pointer-events-none absolute z-10 max-w-[260px] rounded-md border border-border-strong bg-bg-1/95 p-2 text-[11px] shadow-[var(--shadow-popover)] backdrop-blur"
          style={{
            left: Math.min(Math.max(xToPx(hoverX) + 8, 8), width - 200),
            top: PADDING.top,
          }}
        >
          <div className="mb-1 font-mono text-[10px] text-muted-2">x = {formatX(hoverX)}</div>
          {closestPoints.slice(0, 8).map((cp) => (
            <div key={cp.id} className="flex items-center gap-2 leading-tight">
              <span
                aria-hidden
                className="inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full"
                style={{ background: cp.color }}
              />
              <span className="min-w-0 flex-1 truncate font-mono text-text">{cp.label}</span>
              <span className="font-mono tabular-nums text-text">
                {cp.point.y != null ? formatY(cp.point.y) : "—"}
              </span>
            </div>
          ))}
          {closestPoints.length > 8 ? (
            <div className="mt-1 text-[10px] text-muted-2">+{closestPoints.length - 8} more</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function niceTicks(min: number, max: number, target: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min];
  const range = max - min;
  const rough = range / Math.max(target, 1);
  const pow = 10 ** Math.floor(Math.log10(rough));
  const candidates = [1, 2, 2.5, 5, 10].map((m) => m * pow);
  const step = candidates.reduce((best, c) =>
    Math.abs(c - rough) < Math.abs(best - rough) ? c : best,
  );
  const start = Math.ceil(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + 1e-9; v += step) {
    out.push(Number(v.toFixed(8)));
  }
  return out;
}
