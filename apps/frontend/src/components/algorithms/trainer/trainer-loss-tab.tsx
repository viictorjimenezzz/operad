import { TrainingLossCurve } from "@/components/charts/training-loss-curve";
import { EmptyState, PanelCard, Pill } from "@/components/ui";
import { CheckpointEntry, FitnessEntry } from "@/lib/types";
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

interface TrainerLossTabProps {
  dataFitness?: unknown;
  dataCheckpoints?: unknown;
  dataSummary?: unknown;
}

type MetricMode =
  | { id: "loss"; label: string; kind: "loss" }
  | { id: string; label: string; kind: "metric"; keys: string[] };

const FitnessRows = z.array(FitnessEntry);
const CheckpointRows = z.array(
  z
    .object({
      epoch: z.number(),
      metric_snapshot: z.record(z.union([z.number(), z.null()])).optional(),
    })
    .passthrough(),
);

const LOSS_KEYS = new Set(["loss", "train_loss", "val_loss", "best", "mean", "worst", "score"]);

export function TrainerLossTab({ dataFitness, dataCheckpoints, dataSummary }: TrainerLossTabProps) {
  const modes = useMemo(
    () => buildModes(dataCheckpoints, dataSummary),
    [dataCheckpoints, dataSummary],
  );
  const [selectedModeId, setSelectedModeId] = useState<string>("loss");
  const selected = modes.find((mode) => mode.id === selectedModeId) ?? modes[0] ?? { id: "loss", label: "loss", kind: "loss" };

  return (
    <div className="h-full overflow-auto p-4">
      <PanelCard title="loss overlays" bodyMinHeight={320}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {modes.map((mode) => {
            const active = mode.id === selected.id;
            return (
              <button
                key={mode.id}
                type="button"
                onClick={() => setSelectedModeId(mode.id)}
                className={
                  active
                    ? "rounded border border-accent bg-bg-3 px-2 py-1 text-[11px] text-accent"
                    : "rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted"
                }
              >
                {mode.label}
              </button>
            );
          })}
          {selected.kind === "metric" ? <Pill tone="accent">{selected.label}</Pill> : null}
        </div>

        {selected.kind === "loss" ? (
          <TrainingLossCurve data={dataFitness} checkpointData={dataCheckpoints} height={280} />
        ) : (
          <MetricOverlayChart
            dataFitness={dataFitness}
            dataCheckpoints={dataCheckpoints}
            keys={selected.keys}
            label={selected.label}
          />
        )}
      </PanelCard>
    </div>
  );
}

function buildModes(dataCheckpoints: unknown, dataSummary: unknown): MetricMode[] {
  const checkpointMetricKeys = metricKeysFromCheckpoints(dataCheckpoints);
  const summaryMetricKeys = metricKeysFromSummary(dataSummary);
  const merged = [...new Set([...checkpointMetricKeys, ...summaryMetricKeys])];
  const accuracyKeys = merged.filter((key) => /(^|[_-])(acc|accuracy)([_-]|$)/i.test(key));
  const customKeys = merged.filter((key) => !accuracyKeys.includes(key) && !LOSS_KEYS.has(key));

  const modes: MetricMode[] = [{ id: "loss", label: "loss", kind: "loss" }];
  if (accuracyKeys.length > 0) {
    modes.push({ id: "accuracy", label: "accuracy", kind: "metric", keys: accuracyKeys });
  }
  for (const key of customKeys) {
    modes.push({ id: `metric:${key}`, label: key, kind: "metric", keys: [key] });
  }
  return modes;
}

function metricKeysFromCheckpoints(dataCheckpoints: unknown): string[] {
  const parsed = CheckpointRows.safeParse(dataCheckpoints);
  if (!parsed.success) return [];
  const keys = new Set<string>();
  for (const row of parsed.data) {
    const snapshot = row.metric_snapshot;
    if (!snapshot) continue;
    for (const [key, value] of Object.entries(snapshot)) {
      if (typeof value === "number" && Number.isFinite(value)) keys.add(key);
    }
  }
  return [...keys].sort();
}

function metricKeysFromSummary(dataSummary: unknown): string[] {
  if (!dataSummary || typeof dataSummary !== "object" || Array.isArray(dataSummary)) return [];
  const metrics = (dataSummary as Record<string, unknown>).metrics;
  if (!metrics || typeof metrics !== "object" || Array.isArray(metrics)) return [];
  return Object.entries(metrics)
    .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
    .map(([key]) => key)
    .sort();
}

function MetricOverlayChart({
  dataFitness,
  dataCheckpoints,
  keys,
  label,
}: {
  dataFitness: unknown;
  dataCheckpoints: unknown;
  keys: string[];
  label: string;
}) {
  const rows = useMemo(() => buildMetricRows(dataFitness, dataCheckpoints, keys), [dataFitness, dataCheckpoints, keys]);

  if (rows.length === 0) {
    return (
      <EmptyState
        title="no metric history"
        description={`${label} exists in summary metrics but no epoch-level metric_snapshot was emitted`}
      />
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={rows} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="epoch" stroke="var(--color-muted)" tick={{ fontSize: 11 }} />
        <YAxis stroke="var(--color-muted)" tick={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        {keys.map((key, index) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={`var(--qual-${(index % 12) + 1})`}
            strokeWidth={2}
            dot={{ r: 2 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function buildMetricRows(dataFitness: unknown, dataCheckpoints: unknown, keys: string[]) {
  const fitness = FitnessRows.safeParse(dataFitness).data ?? [];
  const checkpoints = CheckpointRows.safeParse(dataCheckpoints).data ?? [];

  const byEpoch = new Map<number, Record<string, number | null>>();
  for (const row of fitness) {
    byEpoch.set(row.gen_index, { epoch: row.gen_index } as Record<string, number | null>);
  }

  for (const row of checkpoints) {
    const existing = byEpoch.get(row.epoch) ?? ({ epoch: row.epoch } as Record<string, number | null>);
    for (const key of keys) {
      const metricValue = row.metric_snapshot?.[key];
      if (typeof metricValue === "number" && Number.isFinite(metricValue)) {
        existing[key] = metricValue;
      }
    }
    byEpoch.set(row.epoch, existing);
  }

  return [...byEpoch.values()]
    .sort((a, b) => Number(a.epoch) - Number(b.epoch))
    .filter((row) => keys.some((key) => typeof row[key] === "number"));
}
