import { EmptyState } from "@/components/ui/empty-state";
import { RunSummary as RunSummarySchema, SweepSnapshot } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

interface SweepParallelCoordsTabProps {
  data: unknown;
  dataChildren?: unknown;
}

const WIDTH = 960;
const HEIGHT = 300;
const PAD_X = 70;
const PAD_TOP = 38;
const PAD_BOTTOM = 26;

export function SweepParallelCoordsTab({ data, dataChildren }: SweepParallelCoordsTabProps) {
  const parsed = SweepSnapshot.safeParse(data);
  const navigate = useNavigate();
  const [hoveredCell, setHoveredCell] = useState<number | null>(null);
  const childrenByCell = useMemo(() => childByCell(dataChildren), [dataChildren]);

  if (!parsed.success || parsed.data.cells.length === 0) {
    return <EmptyState title="no sweep data" description="waiting for cells to complete" />;
  }

  const snap = parsed.data;
  if (snap.axes.length <= 1) {
    return (
      <EmptyState
        title="parallel coordinates unavailable"
        description="parallel coordinates needs at least two sweep axes"
      />
    );
  }

  const scoredValues = snap.cells
    .map((cell) => cell.score)
    .filter((value): value is number => value != null && Number.isFinite(value));
  const [minScore, maxScore] = scoreRange(snap.score_range, scoredValues);
  const axisX = (index: number) =>
    PAD_X + (index / Math.max(1, snap.axes.length - 1)) * (WIDTH - PAD_X * 2);
  const axisHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const hovered = hoveredCell == null ? null : snap.cells.find((cell) => cell.cell_index === hoveredCell);

  return (
    <div className="flex flex-col gap-2">
      <div className="min-h-6 text-[11px] text-muted">
        {hovered ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-mono text-text">cell #{hovered.cell_index}</span>
            <span className="font-mono">score {hovered.score != null ? formatNumber(hovered.score) : "—"}</span>
            {snap.axes.map((axis) => (
              <span key={`${hovered.cell_index}:${axis.name}`} className="font-mono">
                {axis.name}={String(hovered.parameters[axis.name] ?? "—")}
              </span>
            ))}
          </div>
        ) : (
          <span>hover a line to inspect axis values; click a line to open the child run</span>
        )}
      </div>
      <div className="overflow-auto rounded-lg border border-border bg-bg-inset p-2">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label="parallel coordinates"
          className="min-w-[720px]"
        >
          {snap.axes.map((axis, index) => {
            const x = axisX(index);
            return (
              <g key={axis.name}>
                <line x1={x} x2={x} y1={PAD_TOP} y2={HEIGHT - PAD_BOTTOM} stroke="var(--color-border)" />
                <text
                  x={x}
                  y={16}
                  textAnchor="middle"
                  fill="var(--color-muted)"
                  className="text-[11px] font-medium"
                >
                  {axis.name}
                </text>
                {axis.values.map((value, valueIndex) => {
                  const y = axisValueY(valueIndex, axis.values.length, axisHeight);
                  return (
                    <g key={`${axis.name}:${normalizeKey(value)}`}>
                      <line
                        x1={x - 3}
                        x2={x + 3}
                        y1={PAD_TOP + y}
                        y2={PAD_TOP + y}
                        stroke="var(--color-border-strong)"
                        strokeWidth={1}
                      />
                      {index === snap.axes.length - 1 || axis.values.length > 8 ? null : (
                        <text
                          x={x + 6}
                          y={PAD_TOP + y + 3}
                          fill="var(--color-muted-2)"
                          className="text-[9px]"
                        >
                          {String(value)}
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}
          {snap.cells.map((cell) => {
            const child = childrenByCell.get(cell.cell_index);
            const href = child ? childHref(child) : null;
            const points = snap.axes
              .map((axis, index) => {
                const axisIndex = axis.values.findIndex(
                  (candidate) => normalizeKey(candidate) === normalizeKey(cell.parameters[axis.name]),
                );
                const yIndex = axisIndex < 0 ? (axis.values.length - 1) / 2 : axisIndex;
                const y = axisValueY(yIndex, axis.values.length, axisHeight);
                return `${axisX(index)},${PAD_TOP + y}`;
              })
              .join(" ");
            const active = hoveredCell === cell.cell_index;
            return (
              <polyline
                key={cell.cell_index}
                data-cell-line="true"
                points={points}
                fill="none"
                stroke={scoreColor(cell.score, minScore, maxScore)}
                strokeWidth={active ? 2.4 : 1.4}
                strokeOpacity={active ? 1 : hoveredCell == null ? 0.72 : 0.18}
                className={cn(href ? "cursor-pointer" : "cursor-default")}
                onMouseEnter={() => setHoveredCell(cell.cell_index)}
                onMouseLeave={() => setHoveredCell((current) => (current === cell.cell_index ? null : current))}
                onClick={() => {
                  if (!href) return;
                  navigate(href);
                }}
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
}

function childByCell(data: unknown): Map<number, ChildRunSummary> {
  const parsed = z.array(ChildRunSummary).safeParse(data);
  if (!parsed.success) return new Map();
  const sorted = [...parsed.data].sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0));
  return new Map(sorted.map((child, index) => [index, child]));
}

function childHref(child: ChildRunSummary): string {
  const identity = child.hash_content ?? child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function scoreRange(scoreRangeValue: [number, number] | null, values: number[]): [number, number] {
  if (scoreRangeValue && Number.isFinite(scoreRangeValue[0]) && Number.isFinite(scoreRangeValue[1])) {
    return scoreRangeValue;
  }
  if (values.length === 0) return [0, 1];
  let min = values[0] ?? 0;
  let max = values[0] ?? 0;
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return [min, max];
}

function axisValueY(valueIndex: number, valueCount: number, axisHeight: number): number {
  if (valueCount <= 1) return axisHeight / 2;
  return (1 - valueIndex / (valueCount - 1)) * axisHeight;
}

function scoreColor(score: number | null, min: number, max: number): string {
  if (score == null || !Number.isFinite(score)) return "var(--color-muted-2)";
  const t = Math.max(0, Math.min(1, (score - min) / (max - min || 1)));
  const bucket = Math.round(t * 11) + 1;
  return `var(--qual-${Math.max(1, Math.min(12, bucket))})`;
}

function normalizeKey(value: unknown): string {
  if (value === null) return "null:";
  if (value === undefined) return "undefined:";
  return `${typeof value}:${String(value)}`;
}
