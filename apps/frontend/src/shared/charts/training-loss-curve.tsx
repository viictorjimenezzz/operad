import { FitnessEntry } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
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

const FitnessRows = z.array(FitnessEntry);

/**
 * Trainer's per-epoch fitness signal lands in /runs/{id}/fitness.json
 * as `iteration` events with `score`. We re-purpose that endpoint as
 * a loss curve for training runs (Trainer's `iteration` events fire
 * on epoch_end with `score = train_loss` when the trainer wires it
 * that way; otherwise the curve still represents the epoch metric).
 */
export function TrainingLossCurve({ data, height = 220 }: { data: unknown; height?: number }) {
  const parsed = FitnessRows.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no loss data yet" />;
  }
  const rows = [...parsed.data].sort((a, b) => a.gen_index - b.gen_index);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
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
        <YAxis stroke="var(--color-muted)" tick={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        <Line
          type="monotone"
          dataKey="best"
          stroke="var(--color-accent)"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="loss"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
