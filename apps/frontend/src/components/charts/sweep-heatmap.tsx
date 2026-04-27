import type { SweepAggregation } from "@/components/algorithms/sweep/sweep-dimension-picker";
import { EmptyState } from "@/components/ui/empty-state";
import { type SweepCell, SweepSnapshot } from "@/lib/types";
import { formatNumber } from "@/lib/utils";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface SweepHeatmapProps {
  data: unknown;
  xAxis?: string | null;
  yAxis?: string | null;
  aggregations?: Record<string, SweepAggregation>;
  cellHrefs?: Record<number, string>;
}

interface AggregatedCell {
  x: unknown;
  y: unknown | null;
  cells: SweepCell[];
  score: number | null;
}

export function SweepHeatmap({
  data,
  xAxis,
  yAxis,
  aggregations = {},
  cellHrefs = {},
}: SweepHeatmapProps) {
  const parsed = SweepSnapshot.safeParse(data);
  if (!parsed.success || parsed.data.cells.length === 0) {
    return <EmptyState title="no sweep data" description="waiting for cells to complete" />;
  }
  const snap = parsed.data;
  const dims = snap.axes.length;

  if (dims <= 1) {
    return (
      <BarView
        snap={snap}
        xAxis={xAxis ?? snap.axes[0]?.name ?? null}
        aggregations={aggregations}
      />
    );
  }

  const selectedX =
    xAxis && snap.axes.some((axis) => axis.name === xAxis) ? xAxis : snap.axes[0]?.name;
  const selectedY =
    yAxis && yAxis !== selectedX && snap.axes.some((axis) => axis.name === yAxis)
      ? yAxis
      : snap.axes.find((axis) => axis.name !== selectedX)?.name;

  if (!selectedX || !selectedY) {
    return <BarView snap={snap} xAxis={selectedX ?? null} aggregations={aggregations} />;
  }

  return (
    <MatrixView
      snap={snap}
      xAxis={selectedX}
      yAxis={selectedY}
      aggregations={aggregations}
      cellHrefs={cellHrefs}
    />
  );
}

function BarView({
  snap,
  xAxis,
  aggregations,
}: {
  snap: SweepSnapshot;
  xAxis: string | null;
  aggregations: Record<string, SweepAggregation>;
}) {
  const axis = xAxis ? snap.axes.find((candidate) => candidate.name === xAxis) : snap.axes[0];
  if (!axis) {
    return <EmptyState title="no sweep axis" description="cells did not include parameters" />;
  }
  const grouped = aggregateCells(snap, axis.name, null, aggregations);
  const bars = axis.values.map((value) => {
    const entry = grouped.find((cell) => sameValue(cell.x, value));
    return {
      label: String(value),
      score: entry?.score ?? null,
      cells: entry?.cells.length ?? 0,
    };
  });
  const scored = bars.some((bar) => bar.score != null);

  return (
    <div className="relative">
      {!scored ? <ScorelessOverlay /> : null}
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={bars} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip content={<BarTooltip axis={axis.name} />} />
          <Bar
            dataKey={scored ? "score" : "cells"}
            fill={scored ? "var(--color-accent)" : "var(--color-ok)"}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MatrixView({
  snap,
  xAxis,
  yAxis,
  aggregations,
  cellHrefs,
}: {
  snap: SweepSnapshot;
  xAxis: string;
  yAxis: string;
  aggregations: Record<string, SweepAggregation>;
  cellHrefs: Record<number, string>;
}) {
  const ax0 = snap.axes.find((axis) => axis.name === xAxis);
  const ax1 = snap.axes.find((axis) => axis.name === yAxis);
  if (!ax0 || !ax1) {
    return (
      <EmptyState title="not enough dimensions" description="heatmap requires two sweep axes" />
    );
  }

  const [scoreMin, scoreMax] = snap.score_range ?? [0, 1];
  const grouped = aggregateCells(snap, ax0.name, ax1.name, aggregations);
  const map = new Map(grouped.map((cell) => [`${String(cell.x)}||${String(cell.y)}`, cell]));
  const scored = grouped.some((cell) => cell.score != null);

  return (
    <div className="relative overflow-auto">
      {!scored ? <ScorelessOverlay /> : null}
      <table className="border-collapse text-[11px]">
        <thead>
          <tr>
            <th className="sticky left-0 bg-bg-1 px-2 py-1 text-left font-medium text-muted">
              {ax0.name} / {ax1.name}
            </th>
            {ax1.values.map((value) => (
              <th key={String(value)} className="px-2 py-1 text-right font-medium text-muted">
                {String(value)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ax0.values.map((xValue) => (
            <tr key={String(xValue)}>
              <td className="sticky left-0 bg-bg-1 px-2 py-1 font-mono text-text">
                {String(xValue)}
              </td>
              {ax1.values.map((yValue) => {
                const entry = map.get(`${String(xValue)}||${String(yValue)}`) ?? null;
                return (
                  <td key={String(yValue)} className="relative p-0">
                    <HeatmapCell
                      entry={entry}
                      xAxis={ax0.name}
                      yAxis={ax1.name}
                      scoreMin={scoreMin}
                      scoreMax={scoreMax}
                      scored={scored}
                      cellHrefs={cellHrefs}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HeatmapCell({
  entry,
  xAxis,
  yAxis,
  scoreMin,
  scoreMax,
  scored,
  cellHrefs,
}: {
  entry: AggregatedCell | null;
  xAxis: string;
  yAxis: string;
  scoreMin: number;
  scoreMax: number;
  scored: boolean;
  cellHrefs: Record<number, string>;
}) {
  const score = entry?.score ?? null;
  const background = scored
    ? scoreColor(score, scoreMin, scoreMax)
    : entry && entry.cells.length > 0
      ? "var(--color-ok-dim)"
      : "transparent";
  return (
    <div
      className="group min-w-20 px-2 py-1 text-right font-mono tabular-nums"
      style={{ background }}
    >
      {score != null ? score.toFixed(3) : ""}
      <div className="absolute left-1/2 top-full z-30 hidden w-72 -translate-x-1/2 rounded border border-border-strong bg-bg-1 p-2 text-left font-sans text-[11px] shadow-[var(--shadow-popover)] group-hover:block">
        {entry ? (
          <div className="flex flex-col gap-1">
            <div className="font-mono text-text">
              {xAxis}={String(entry.x)}, {yAxis}={String(entry.y)}
            </div>
            <div className="text-muted">
              score:{" "}
              <span className="font-mono text-text">
                {entry.score != null ? entry.score.toFixed(4) : "unscored"}
              </span>
              {entry.cells.length > 1 ? ` (${entry.cells.length} cells)` : ""}
            </div>
            <div className="max-h-24 overflow-auto text-muted-2">
              {entry.cells.slice(0, 5).map((cell) => (
                <div key={cell.cell_index} className="truncate">
                  cell #{cell.cell_index}: {parametersLabel(cell.parameters)}
                  {cellHrefs[cell.cell_index] ? (
                    <a
                      href={cellHrefs[cell.cell_index]}
                      className="ml-2 text-accent hover:text-[--color-accent-strong]"
                    >
                      open
                    </a>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-muted">pending cell</div>
        )}
      </div>
    </div>
  );
}

function ScorelessOverlay() {
  return (
    <div className="pointer-events-none absolute inset-x-4 top-4 z-20 rounded border border-[--color-warn-dim] bg-bg-1/95 p-3 text-center text-[12px] text-muted shadow-[var(--shadow-card-soft)]">
      this sweep did not define a score function - open individual cell runs for results
    </div>
  );
}

function aggregateCells(
  snap: SweepSnapshot,
  xAxis: string,
  yAxis: string | null,
  aggregations: Record<string, SweepAggregation>,
): AggregatedCell[] {
  const groups = new Map<string, AggregatedCell>();
  for (const cell of snap.cells) {
    const x = cell.parameters[xAxis] ?? null;
    const y = yAxis ? (cell.parameters[yAxis] ?? null) : null;
    const key = `${String(x)}||${String(y)}`;
    const existing = groups.get(key);
    if (existing) existing.cells.push(cell);
    else groups.set(key, { x, y, cells: [cell], score: null });
  }

  return [...groups.values()].map((group) => {
    const unselected = snap.axes.filter((axis) => axis.name !== xAxis && axis.name !== yAxis);
    const agg =
      unselected.length === 1 ? (aggregations[unselected[0]?.name ?? ""] ?? "mean") : "mean";
    return { ...group, score: aggregateScore(group.cells, agg) };
  });
}

function aggregateScore(cells: SweepCell[], aggregation: SweepAggregation): number | null {
  if (aggregation === "count") return cells.length;
  const scores = cells
    .map((cell) => cell.score)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));
  if (scores.length === 0) return null;
  if (aggregation === "min") return Math.min(...scores);
  if (aggregation === "max") return Math.max(...scores);
  if (aggregation === "median") {
    const sorted = [...scores].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    const value =
      sorted.length % 2 === 0
        ? ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2
        : (sorted[mid] ?? 0);
    return value;
  }
  return scores.reduce((sum, score) => sum + score, 0) / scores.length;
}

function scoreColor(score: number | null, min: number, max: number): string {
  if (score == null) return "transparent";
  const t = Math.max(0, Math.min(1, (score - min) / (max - min || 1)));
  if (t > 0.7) return "color-mix(in srgb, var(--color-ok) 52%, transparent)";
  if (t > 0.35) return "color-mix(in srgb, var(--color-accent) 42%, transparent)";
  return "color-mix(in srgb, var(--color-warn) 30%, transparent)";
}

function sameValue(a: unknown, b: unknown): boolean {
  return String(a) === String(b);
}

function parametersLabel(parameters: Record<string, unknown>): string {
  return Object.entries(parameters)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(", ");
}

function BarTooltip({
  active,
  payload,
  label,
  axis,
}: {
  active?: boolean;
  payload?: Array<{ value?: unknown }>;
  label?: string;
  axis: string;
}) {
  if (!active) return null;
  const value = payload?.[0]?.value;
  return (
    <div className="rounded border border-border bg-bg-1 p-2 text-[11px] shadow-[var(--shadow-popover)]">
      <div className="font-mono text-text">
        {axis}={label}
      </div>
      <div className="text-muted">
        value: {typeof value === "number" ? formatNumber(value) : "-"}
      </div>
    </div>
  );
}
