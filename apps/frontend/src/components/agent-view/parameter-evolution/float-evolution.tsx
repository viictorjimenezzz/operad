import { EmptyState } from "@/components/ui";
import { hashColor, hashColorDim } from "@/lib/hash-color";
import { formatNumber } from "@/lib/utils";
import { useMemo } from "react";

export type ParameterEvolutionPoint = {
  runId: string;
  startedAt: number;
  value: unknown;
  hash: string;
};

export type FloatConstraint = {
  default?: number | null;
  min?: number | null;
  max?: number | null;
};

export interface FloatEvolutionProps {
  path: string;
  points: ParameterEvolutionPoint[];
  constraint?: FloatConstraint | undefined;
  selectedStep?: number | undefined;
  onSelectStep?: ((step: number) => void) | undefined;
  compact?: boolean | undefined;
}

const WIDTH = 640;
const HEIGHT = 180;
const PAD = { top: 14, right: 14, bottom: 24, left: 42 };

export function FloatEvolution({
  path,
  points,
  constraint,
  selectedStep,
  onSelectStep,
  compact,
}: FloatEvolutionProps) {
  const values = useMemo(() => points.map((point, index) => toPoint(point.value, index)), [points]);
  const finiteValues = values.filter((point) => point.y != null) as Array<{ x: number; y: number }>;

  if (points.length === 0) {
    return (
      <EmptyState
        title="no numeric parameter history"
        description="this parameter has no recorded evolution points yet"
      />
    );
  }

  if (finiteValues.length === 0) {
    return (
      <EmptyState
        title="no numeric values"
        description="recorded points for this parameter are not numeric"
      />
    );
  }

  const references = referenceLines(constraint);
  const domainValues = [
    ...finiteValues.map((point) => point.y),
    ...references.map((line) => line.y),
  ];
  const yMin = Math.min(...domainValues);
  const yMax = Math.max(...domainValues);
  const ySpan = Math.max(yMax - yMin, 1e-9);
  const xSpan = Math.max(points.length - 1, 1);
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const xToPx = (x: number) => PAD.left + (x / xSpan) * innerW;
  const yToPx = (y: number) => PAD.top + (1 - (y - yMin) / ySpan) * innerH;
  const selected = selectedStep != null ? values[selectedStep] : undefined;
  const selectedValue = selected?.y;
  const stats = summarize(finiteValues.map((point) => point.y));

  return (
    <div className="space-y-2" data-testid="float-evolution">
      <div className="relative overflow-hidden rounded-md border border-border bg-bg-1">
        <svg
          width="100%"
          height={compact ? 128 : HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`${path} step plot`}
        >
          <title>{path} step plot</title>
          {niceTicks(yMin, yMax, 4).map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={yToPx(tick)}
                y2={yToPx(tick)}
                stroke="var(--color-border)"
                strokeDasharray="2 3"
                opacity={0.6}
              />
              <text
                x={PAD.left - 6}
                y={yToPx(tick)}
                textAnchor="end"
                dominantBaseline="central"
                fontSize={10}
                fill="var(--color-muted-2)"
              >
                {formatNumber(tick)}
              </text>
            </g>
          ))}
          {references.map((line) => (
            <g key={line.label}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={yToPx(line.y)}
                y2={yToPx(line.y)}
                stroke="var(--color-muted)"
                strokeDasharray={line.dashed ? "5 4" : "2 3"}
                opacity={line.dashed ? 0.7 : 0.45}
              />
              <text
                x={WIDTH - PAD.right - 4}
                y={yToPx(line.y) - 4}
                textAnchor="end"
                fontSize={10}
                fill="var(--color-muted-2)"
              >
                {line.label}
              </text>
            </g>
          ))}
          <path
            d={stepPath(finiteValues, xToPx, yToPx)}
            fill="none"
            stroke={hashColor(path)}
            strokeWidth={2}
            strokeLinejoin="round"
          />
          {finiteValues.map((point) => (
            <circle
              key={point.x}
              cx={xToPx(point.x)}
              cy={yToPx(point.y)}
              r={2.8}
              fill={hashColor(path)}
              stroke="var(--color-bg-1)"
              strokeWidth={1.5}
            />
          ))}
          {selectedStep != null && selectedStep >= 0 && selectedStep < points.length ? (
            <line
              x1={xToPx(selectedStep)}
              x2={xToPx(selectedStep)}
              y1={PAD.top}
              y2={HEIGHT - PAD.bottom}
              stroke="var(--color-border-strong)"
              strokeWidth={1.5}
            />
          ) : null}
          {points.map((point, index) => (
            <rect
              key={point.runId}
              role="button"
              tabIndex={0}
              aria-label={`select step ${index}`}
              x={xToPx(index) - Math.max(innerW / Math.max(points.length, 1) / 2, 8)}
              y={PAD.top}
              width={Math.max(innerW / Math.max(points.length, 1), 16)}
              height={innerH}
              fill="transparent"
              onClick={() => onSelectStep?.(index)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") onSelectStep?.(index);
              }}
            />
          ))}
          <text
            x={WIDTH - PAD.right}
            y={HEIGHT - 6}
            textAnchor="end"
            fontSize={10}
            fill="var(--color-muted-2)"
          >
            step
          </text>
        </svg>
      </div>
      <div className="grid grid-cols-3 border-y border-border text-[11px]">
        <Stat label="min" value={stats.min} />
        <Stat label="max" value={stats.max} />
        <Stat label="mean" value={stats.mean} />
      </div>
      {selectedStep != null && selectedValue != null ? (
        <div
          className="inline-flex items-center gap-2 rounded border border-border px-2 py-1 font-mono text-[11px]"
          style={{ background: hashColorDim(path, 0.18) }}
        >
          <span className="text-muted-2">step {selectedStep}</span>
          <span className="text-text">{formatNumber(selectedValue)}</span>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between border-r border-border px-2 py-1 last:border-r-0">
      <span className="text-muted-2">{label}</span>
      <span className="font-mono tabular-nums text-text">{formatNumber(value)}</span>
    </div>
  );
}

function toPoint(value: unknown, index: number): { x: number; y: number | null } {
  return { x: index, y: toNumber(value) };
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return null;
}

function referenceLines(constraint: FloatConstraint | undefined) {
  const lines: Array<{ y: number; label: string; dashed: boolean }> = [];
  const defaultValue = constraint?.default;
  const min = constraint?.min;
  const max = constraint?.max;
  if (Number.isFinite(defaultValue)) {
    lines.push({ y: defaultValue as number, label: "default", dashed: false });
  }
  if (Number.isFinite(min)) {
    lines.push({ y: min as number, label: "min", dashed: true });
  }
  if (Number.isFinite(max)) {
    lines.push({ y: max as number, label: "max", dashed: true });
  }
  return lines;
}

function summarize(values: number[]) {
  const total = values.reduce((sum, value) => sum + value, 0);
  return {
    min: Math.min(...values),
    max: Math.max(...values),
    mean: total / values.length,
  };
}

function stepPath(
  points: Array<{ x: number; y: number }>,
  xToPx: (x: number) => number,
  yToPx: (y: number) => number,
): string {
  const first = points[0];
  if (!first) return "";
  const parts = [`M ${xToPx(first.x).toFixed(2)} ${yToPx(first.y).toFixed(2)}`];
  for (const point of points.slice(1)) {
    parts.push(`H ${xToPx(point.x).toFixed(2)}`);
    parts.push(`V ${yToPx(point.y).toFixed(2)}`);
  }
  return parts.join(" ");
}

function niceTicks(min: number, max: number, target: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min];
  const range = max - min;
  const rough = range / Math.max(target, 1);
  const pow = 10 ** Math.floor(Math.log10(rough));
  const candidates = [1, 2, 2.5, 5, 10].map((m) => m * pow);
  const step = candidates.reduce((best, candidate) =>
    Math.abs(candidate - rough) < Math.abs(best - rough) ? candidate : best,
  );
  const start = Math.ceil(min / step) * step;
  const out: number[] = [];
  for (let value = start; value <= max + 1e-9; value += step) {
    out.push(Number(value.toFixed(8)));
  }
  return out;
}
