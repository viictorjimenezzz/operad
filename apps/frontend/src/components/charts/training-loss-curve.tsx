import { EmptyState } from "@/components/ui/empty-state";
import { CheckpointEntry, FitnessEntry } from "@/lib/types";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

const FitnessRows = z.array(FitnessEntry);
const CheckpointRows = z.array(CheckpointEntry);

export function TrainingLossCurve({
  data,
  checkpointData,
  height = 220,
}: {
  data: unknown;
  checkpointData?: unknown;
  height?: number;
}) {
  const parsed = FitnessRows.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no loss data yet" />;
  }
  const rows = [...parsed.data].sort((a, b) => a.gen_index - b.gen_index);

  const checkpoints = CheckpointRows.safeParse(checkpointData).data ?? [];
  const bestCheckpoint = checkpoints.find((c) => c.is_best);

  // Merge val_loss from checkpoints into rows keyed by epoch (gen_index)
  const valByEpoch = new Map(checkpoints.map((c) => [c.epoch, c.val_loss]));
  const merged = rows.map((r) => ({
    ...r,
    train_loss: r.train_loss ?? r.best,
    val_loss: valByEpoch.get(r.gen_index) ?? null,
    lr: r.lr ?? null,
  }));

  const hasVal = merged.some((r) => r.val_loss != null);
  const hasLr = merged.some((r) => r.lr != null);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={merged} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis
          dataKey="gen_index"
          stroke="var(--color-muted)"
          tick={{ fontSize: 11 }}
          label={{
            value: "epoch",
            position: "insideBottomRight",
            offset: -2,
            style: { fill: "var(--color-muted)", fontSize: 10 },
          }}
        />
        <YAxis yAxisId="left" stroke="var(--color-muted)" tick={{ fontSize: 11 }} />
        {hasLr && (
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="var(--color-muted)"
            tick={{ fontSize: 11 }}
          />
        )}
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        <Line
          type="monotone"
          yAxisId="left"
          dataKey="train_loss"
          stroke="var(--color-accent)"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="train loss"
        />
        {hasVal && (
          <Line
            type="monotone"
            yAxisId="left"
            dataKey="val_loss"
            stroke="var(--color-warn)"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={{ r: 3 }}
            name="val loss"
            connectNulls
          />
        )}
        {hasLr && (
          <Line
            type="monotone"
            yAxisId="right"
            dataKey="lr"
            stroke="var(--color-algo)"
            strokeWidth={1.5}
            dot={false}
            name="lr"
            connectNulls
          />
        )}
        {bestCheckpoint != null && (
          <ReferenceLine
            x={bestCheckpoint.epoch}
            stroke="var(--color-accent)"
            strokeDasharray="4 2"
            label={{
              value: "best",
              position: "top",
              style: { fill: "var(--color-accent)", fontSize: 10 },
            }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
