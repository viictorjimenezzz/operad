import { cn } from "@/lib/utils";
import { useMemo } from "react";

export interface SparklineProps {
  values: Array<number | null | undefined>;
  width?: number;
  height?: number;
  className?: string;
  /** Render dots on each data point (default false). */
  dots?: boolean;
  /** Stroke color override; falls back to currentColor. */
  color?: string;
  /** Show a subtle gradient fill below the line. */
  filled?: boolean;
}

export function Sparkline({
  values,
  width = 80,
  height = 22,
  className,
  dots = false,
  color,
  filled = true,
}: SparklineProps) {
  const points = useMemo(() => {
    const cleaned = values
      .map((v) => (typeof v === "number" && Number.isFinite(v) ? v : null))
      .map((v, i) => ({ v, i }));
    const finite = cleaned.filter((p) => p.v != null) as { v: number; i: number }[];
    if (finite.length < 2) return null;
    const min = Math.min(...finite.map((p) => p.v));
    const max = Math.max(...finite.map((p) => p.v));
    const span = Math.max(max - min, 1e-9);
    const stepX = width / Math.max(values.length - 1, 1);
    const padY = 2;
    const innerH = height - padY * 2;
    return finite.map(({ v, i }) => ({
      x: i * stepX,
      y: padY + innerH - ((v - min) / span) * innerH,
    }));
  }, [values, width, height]);

  const stroke = color ?? "currentColor";
  const gradId = useMemo(() => `sg-${Math.random().toString(36).slice(2, 8)}`, []);

  if (!points) {
    return (
      <span
        className={cn("inline-block text-muted-2", className)}
        style={{ width, height, fontSize: "10px", lineHeight: `${height}px` }}
      >
        —
      </span>
    );
  }

  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) {
    return null;
  }
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible text-accent", className)}
      role="img"
      aria-label="sparkline"
    >
      <title>sparkline</title>
      {filled ? (
        <>
          <defs>
            <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
              <stop offset="100%" stopColor={stroke} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d={`${path} L ${last.x} ${height} L ${first.x} ${height} Z`}
            fill={`url(#${gradId})`}
          />
        </>
      ) : null}
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {dots
        ? points.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="1.5" fill={stroke} />)
        : null}
      <circle cx={last.x} cy={last.y} r="2" fill={stroke} />
    </svg>
  );
}
