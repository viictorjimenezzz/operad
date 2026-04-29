import { EmptyState } from "@/components/ui/empty-state";
import { RunSummary as RunSummarySchema, SweepSnapshot } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
  metadata: z.record(z.unknown()).optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

interface SweepParallelCoordsTabProps {
  data: unknown;
  dataChildren?: unknown;
}

const WIDTH = 1120;
const HEIGHT = 380;
const PAD_LEFT = 120;
const PAD_RIGHT = 170;
const PAD_TOP = 72;
const PAD_BOTTOM = 72;

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
    PAD_LEFT + (index / Math.max(1, snap.axes.length - 1)) * (WIDTH - PAD_LEFT - PAD_RIGHT);
  const axisHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const hovered =
    hoveredCell == null ? null : snap.cells.find((cell) => cell.cell_index === hoveredCell);

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="min-h-6 text-[11px] text-muted">
        {hovered ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-mono text-text">cell #{hovered.cell_index}</span>
            <span className="font-mono">
              score {hovered.score != null ? formatNumber(hovered.score) : "—"}
            </span>
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
      <div className="overflow-auto rounded-lg border border-border bg-bg-inset p-3">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label="parallel coordinates"
          className="min-w-[860px]"
        >
          <defs>
            <filter id="sweep-label-bg" x="-10%" y="-10%" width="120%" height="120%">
              <feFlood floodColor="var(--color-bg-1)" floodOpacity="0.92" />
              <feComposite in2="SourceGraphic" operator="over" />
            </filter>
          </defs>
          {snap.axes.map((axis, index) => {
            const x = axisX(index);
            return (
              <g key={axis.name}>
                <line
                  x1={x}
                  x2={x}
                  y1={PAD_TOP}
                  y2={HEIGHT - PAD_BOTTOM}
                  stroke="var(--color-border)"
                />
                <text
                  x={x}
                  y={22}
                  textAnchor="middle"
                  fill="var(--color-muted)"
                  className="text-[11px] font-medium"
                >
                  {axisLabel(axis.name)}
                  <title>{axis.name}</title>
                </text>
                {axis.values.map((value, valueIndex) => {
                  const y = axisValueY(valueIndex, axis.values.length, axisHeight);
                  const labelSide = index === snap.axes.length - 1 ? -1 : 1;
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
                      {axis.values.length > 10 ? null : (
                        <text
                          x={x + labelSide * 8}
                          y={PAD_TOP + y + 3}
                          textAnchor={labelSide < 0 ? "end" : "start"}
                          fill="var(--color-muted-2)"
                          className="text-[9px]"
                          filter="url(#sweep-label-bg)"
                        >
                          {valueLabel(value)}
                          <title>{String(value)}</title>
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}
          {snap.cells.map((cell, lineIndex) => {
            const child = childrenByCell.get(cell.cell_index);
            const href = child
              ? childHref(child)
              : cell.child_run_id
                ? childHrefFromRunId(cell.child_run_id)
                : null;
            const points = snap.axes
              .map((axis, index) => {
                const axisIndex = axis.values.findIndex(
                  (candidate) =>
                    normalizeKey(candidate) === normalizeKey(cell.parameters[axis.name]),
                );
                const yIndex = axisIndex < 0 ? (axis.values.length - 1) / 2 : axisIndex;
                const y = axisValueY(yIndex, axis.values.length, axisHeight);
                return `${axisX(index)},${PAD_TOP + y}`;
              })
              .join(" ");
            const active = hoveredCell === cell.cell_index;
            const lineColor = scoreColor(cell.score, minScore, maxScore);
            const endPoint = lastPoint(points);
            const labelY = endPoint ? endPoint.y + labelOffset(lineIndex) : 0;
            return (
              <g key={cell.cell_index}>
                <polyline
                  points={points}
                  fill="none"
                  stroke={lineColor}
                  strokeWidth={active ? 2.8 : 1.6}
                  strokeOpacity={active ? 1 : hoveredCell == null ? 0.7 : 0.16}
                  pointerEvents="none"
                />
                <polyline
                  data-cell-line="true"
                  points={points}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                  role={href ? "link" : undefined}
                  tabIndex={href ? 0 : undefined}
                  aria-label={href ? `open sweep cell ${cell.cell_index}` : undefined}
                  className={cn(href ? "cursor-pointer" : "cursor-default")}
                  onMouseEnter={() => setHoveredCell(cell.cell_index)}
                  onMouseLeave={() =>
                    setHoveredCell((current) => (current === cell.cell_index ? null : current))
                  }
                  onClick={() => {
                    if (!href) return;
                    navigate(href);
                  }}
                  onKeyDown={(event) => {
                    if (!href || (event.key !== "Enter" && event.key !== " ")) return;
                    event.preventDefault();
                    navigate(href);
                  }}
                />
                {endPoint ? (
                  <text
                    x={WIDTH - PAD_RIGHT + 28}
                    y={Math.max(PAD_TOP, Math.min(HEIGHT - PAD_BOTTOM, labelY))}
                    fill={lineColor}
                    className="text-[10px] font-mono"
                    filter="url(#sweep-label-bg)"
                  >
                    #{cell.cell_index} {cell.score != null ? cell.score.toFixed(3) : "unscored"}
                  </text>
                ) : null}
              </g>
            );
          })}
          <g transform={`translate(${PAD_LEFT}, ${HEIGHT - 28})`}>
            <text x={0} y={0} fill="var(--color-muted-2)" className="text-[10px]">
              low score
            </text>
            {Array.from({ length: 6 }, (_, index) => (
              <rect
                key={index}
                x={62 + index * 20}
                y={-9}
                width={16}
                height={8}
                rx={2}
                fill={`var(--qual-${index * 2 + 1})`}
              />
            ))}
            <text x={190} y={0} fill="var(--color-muted-2)" className="text-[10px]">
              high score
            </text>
          </g>
        </svg>
      </div>
    </div>
  );
}

function childByCell(data: unknown): Map<number, ChildRunSummary> {
  const parsed = z.array(ChildRunSummary).safeParse(data);
  if (!parsed.success) return new Map();
  const sorted = [...parsed.data]
    .filter((child) => metadataString(child, "algorithm_role") !== "sweep_judge")
    .sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0));
  return new Map(
    sorted.map((child, index) => [metadataNumber(child, "cell_index") ?? index, child]),
  );
}

function childHref(child: ChildRunSummary): string {
  const identity = child.hash_content ?? child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function childHrefFromRunId(runId: string): string {
  return `/agents/${encodeURIComponent(runId)}/runs/${encodeURIComponent(runId)}`;
}

function scoreRange(scoreRangeValue: [number, number] | null, values: number[]): [number, number] {
  if (
    scoreRangeValue &&
    Number.isFinite(scoreRangeValue[0]) &&
    Number.isFinite(scoreRangeValue[1])
  ) {
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

function axisLabel(value: string): string {
  const label = value.replace(/^config\.sampling\./, "");
  return label.length > 24 ? `${label.slice(0, 21)}...` : label;
}

function valueLabel(value: unknown): string {
  const label = String(value);
  return label.length > 18 ? `${label.slice(0, 15)}...` : label;
}

function lastPoint(points: string): { x: number; y: number } | null {
  const raw = points.split(" ").at(-1);
  if (!raw) return null;
  const [xRaw, yRaw] = raw.split(",");
  const x = Number(xRaw);
  const y = Number(yRaw);
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}

function labelOffset(index: number): number {
  return ((index % 5) - 2) * 10;
}

function metadataNumber(child: ChildRunSummary, key: string): number | null {
  const value = child.metadata?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function metadataString(child: ChildRunSummary, key: string): string | null {
  const value = child.metadata?.[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}
