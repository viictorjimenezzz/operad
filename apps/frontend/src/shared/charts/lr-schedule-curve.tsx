import { FitnessEntry } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";

const FitnessRows = z.array(FitnessEntry);

export function LrScheduleCurve({ data, height = 220 }: { data: unknown; height?: number }) {
  const parsed = FitnessRows.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no LR schedule data" description="Trainer has not emitted loss/LR events yet" />;
  }
  const rows = parsed.data
    .filter((r) => r.lr != null)
    .sort((a, b) => a.gen_index - b.gen_index)
    .map((r) => ({ step: r.gen_index, lr: r.lr as number }));

  if (rows.length === 0) {
    return <EmptyState title="no LR schedule data" description="Trainer has not emitted loss/LR events yet" />;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="step" stroke="var(--color-muted)" tick={{ fontSize: 11 }} />
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
          dataKey="lr"
          stroke="var(--color-algo)"
          strokeWidth={2}
          dot={false}
          name="lr"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
