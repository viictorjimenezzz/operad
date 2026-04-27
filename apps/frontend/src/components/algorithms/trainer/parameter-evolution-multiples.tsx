import { ParameterDiffPanel } from "@/components/agent-view/group/parameter-diff-panel";
import { EmptyState, HashTag, PanelCard, PanelGrid } from "@/components/ui";
import { CheckpointEntry } from "@/lib/types";
import { formatNumber, truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

export type ParameterEpochPoint = {
  epoch: number;
  value: unknown;
  hash: string;
};

export type ParameterEpochSeries = {
  path: string;
  points: ParameterEpochPoint[];
  kind: "numeric" | "categorical" | "text";
};

interface ParameterEvolutionMultiplesProps {
  dataCheckpoints?: unknown;
  dataSummary?: unknown;
  compact?: boolean;
}

const CheckpointRows = z.array(CheckpointEntry);
const SummarySnapshots = z
  .object({
    parameter_snapshots: z
      .array(
        z
          .object({
            epoch: z.number().optional(),
            values: z.record(z.unknown()).optional(),
          })
          .passthrough(),
      )
      .optional(),
  })
  .passthrough();

export function ParameterEvolutionMultiples({
  dataCheckpoints,
  dataSummary,
  compact,
}: ParameterEvolutionMultiplesProps) {
  const series = useMemo(
    () => extractParameterSeries(dataCheckpoints, dataSummary),
    [dataCheckpoints, dataSummary],
  );
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const selected = series.find((item) => item.path === selectedPath) ?? series[0] ?? null;

  if (series.length === 0) {
    return (
      <EmptyState
        title="no parameter snapshots"
        description="epoch_end events have not captured parameter values yet"
      />
    );
  }

  return (
    <div className="space-y-3">
      <PanelGrid cols={compact ? 2 : 3}>
        {series.map((item) => (
          <button
            key={item.path}
            type="button"
            onClick={() => setSelectedPath(item.path)}
            className="min-w-0 text-left"
          >
            <PanelCard
              title={item.path}
              eyebrow={`${item.points.length} epoch${item.points.length === 1 ? "" : "s"}`}
              bodyMinHeight={compact ? 132 : 166}
              className={selected?.path === item.path ? "border-accent" : undefined}
            >
              <MiniChart series={item} height={compact ? 86 : 118} />
            </PanelCard>
          </button>
        ))}
      </PanelGrid>
      {selected ? <ParameterDiffDrawer series={selected} /> : null}
    </div>
  );
}

export function extractParameterSeries(
  dataCheckpoints?: unknown,
  dataSummary?: unknown,
): ParameterEpochSeries[] {
  const rows = checkpointRows(dataCheckpoints, dataSummary);
  const byPath = new Map<string, ParameterEpochPoint[]>();
  for (const row of rows) {
    for (const [path, value] of Object.entries(row.values)) {
      const existing = byPath.get(path) ?? [];
      existing.push({
        epoch: row.epoch,
        value,
        hash: stableHash(value),
      });
      byPath.set(path, existing);
    }
  }
  return [...byPath.entries()]
    .map(([path, points]) => ({
      path,
      points: points.sort((a, b) => a.epoch - b.epoch),
      kind: classify(points.map((point) => point.value)),
    }))
    .sort((a, b) => a.path.localeCompare(b.path));
}

export function MiniChart({
  series,
  height = 118,
}: { series: ParameterEpochSeries; height?: number }) {
  if (series.kind === "numeric") return <NumericChart series={series} height={height} />;
  if (series.kind === "categorical") return <CategoryChart series={series} height={height} />;
  return <HashLane series={series} />;
}

function NumericChart({ series, height }: { series: ParameterEpochSeries; height: number }) {
  const rows = series.points.map((point) => ({
    epoch: point.epoch,
    value: toNumber(point.value),
  }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="epoch" tick={{ fontSize: 10 }} stroke="var(--color-muted)" />
        <YAxis tick={{ fontSize: 10 }} stroke="var(--color-muted)" width={34} />
        <Tooltip
          formatter={(value) => formatNumber(typeof value === "number" ? value : null)}
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="var(--qual-7)"
          strokeWidth={2}
          dot={{ r: 2 }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function CategoryChart({ series, height }: { series: ParameterEpochSeries; height: number }) {
  const labels = [...new Set(series.points.map((point) => stringifyValue(point.value)))];
  const index = new Map(labels.map((label, i) => [label, i]));
  const rows = series.points.map((point) => ({
    epoch: point.epoch,
    value: index.get(stringifyValue(point.value)) ?? 0,
    label: stringifyValue(point.value),
  }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="epoch" tick={{ fontSize: 10 }} stroke="var(--color-muted)" />
        <YAxis
          tick={{ fontSize: 10 }}
          stroke="var(--color-muted)"
          width={46}
          tickFormatter={(value) => truncateMiddle(labels[value] ?? "", 8)}
        />
        <Tooltip
          formatter={(_, __, item) => (item.payload as { label?: string }).label ?? ""}
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        <Line
          type="stepAfter"
          dataKey="value"
          stroke="var(--qual-6)"
          strokeWidth={2}
          dot={{ r: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function HashLane({ series }: { series: ParameterEpochSeries }) {
  return (
    <div
      className="grid min-w-0 gap-1 overflow-auto"
      style={{
        gridTemplateColumns: `repeat(${Math.max(series.points.length, 1)}, minmax(28px, 1fr))`,
      }}
    >
      {series.points.map((point) => (
        <div key={point.epoch} className="min-w-0">
          <div className="mb-1 truncate text-center font-mono text-[10px] text-muted-2">
            {point.epoch}
          </div>
          <div
            className="h-10 rounded border border-border"
            title={stringifyValue(point.value)}
            style={{ background: `var(--qual-${(hashBucket(point.hash) % 12) + 1})` }}
          />
          <div className="mt-1 truncate text-center font-mono text-[10px] text-muted">
            {truncateMiddle(stringifyValue(point.value), 10)}
          </div>
        </div>
      ))}
    </div>
  );
}

function ParameterDiffDrawer({ series }: { series: ParameterEpochSeries }) {
  const first = series.points[0] ?? null;
  const last = series.points.at(-1) ?? null;
  const [fromEpoch, setFromEpoch] = useState(first?.epoch ?? 0);
  const [toEpoch, setToEpoch] = useState(last?.epoch ?? 0);
  const from = series.points.find((point) => point.epoch === fromEpoch) ?? first;
  const to = series.points.find((point) => point.epoch === toEpoch) ?? last;

  if (!from || !to) return null;

  return (
    <PanelCard title="parameter diff" eyebrow={series.path}>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <label className="flex items-center gap-1.5 text-muted">
          from
          <select
            value={from.epoch}
            onChange={(event) => setFromEpoch(Number(event.target.value))}
            className="rounded border border-border bg-bg-2 px-2 py-1 text-text"
          >
            {series.points.map((point) => (
              <option key={point.epoch} value={point.epoch}>
                epoch {point.epoch}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-muted">
          to
          <select
            value={to.epoch}
            onChange={(event) => setToEpoch(Number(event.target.value))}
            className="rounded border border-border bg-bg-2 px-2 py-1 text-text"
          >
            {series.points.map((point) => (
              <option key={point.epoch} value={point.epoch}>
                epoch {point.epoch}
              </option>
            ))}
          </select>
        </label>
        <HashTag hash={to.hash} mono size="sm" />
      </div>
      <ParameterDiffPanel path={series.path} previous={from.value} current={to.value} />
    </PanelCard>
  );
}

function checkpointRows(dataCheckpoints?: unknown, dataSummary?: unknown) {
  const checkpoints = CheckpointRows.safeParse(dataCheckpoints);
  if (checkpoints.success && checkpoints.data.length > 0) {
    return checkpoints.data
      .filter((row) => row.parameter_snapshot && Object.keys(row.parameter_snapshot).length > 0)
      .map((row) => ({
        epoch: row.epoch,
        values: row.parameter_snapshot ?? {},
      }));
  }

  const summary = SummarySnapshots.safeParse(dataSummary);
  if (!summary.success) return [];
  return (summary.data.parameter_snapshots ?? [])
    .filter((snapshot) => snapshot.values && Object.keys(snapshot.values).length > 0)
    .map((snapshot, index) => ({
      epoch: snapshot.epoch ?? index,
      values: snapshot.values ?? {},
    }));
}

function classify(values: unknown[]): ParameterEpochSeries["kind"] {
  if (values.length > 0 && values.every((value) => toNumber(value) != null)) {
    return "numeric";
  }
  const labels = values.map(stringifyValue);
  const distinct = new Set(labels);
  const compactEnum = labels.every(
    (label) => label.length <= 32 && !/\s/.test(label) && !/^['"]/.test(label),
  );
  if (distinct.size <= 8 && compactEnum) {
    return "categorical";
  }
  return "text";
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return null;
  const stripped = value.trim().replace(/^['"]|['"]$/g, "");
  if (stripped === "") return null;
  const n = Number(stripped);
  return Number.isFinite(n) ? n : null;
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function stableHash(value: unknown): string {
  const text = stringifyValue(value);
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(16).padStart(8, "0").slice(0, 16);
}

function hashBucket(hash: string): number {
  let out = 0;
  for (let i = 0; i < hash.length; i += 1) {
    out = (out * 31 + hash.charCodeAt(i)) | 0;
  }
  return Math.abs(out);
}
