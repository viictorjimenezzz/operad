import { EmptyState } from "@/components/ui/empty-state";
import { FitnessEntry } from "@/lib/types";
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

interface FitnessCurveProps {
  data: unknown;
  height?: number;
}

export function FitnessCurve({ data, height = 220 }: FitnessCurveProps) {
  const parsed = FitnessRows.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return (
      <EmptyState title="no fitness data yet" description="generation events haven't arrived" />
    );
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
            value: "generation",
            position: "insideBottomRight",
            offset: -2,
            style: { fill: "var(--color-muted)", fontSize: 10 },
          }}
        />
        <YAxis stroke="var(--color-muted)" tick={{ fontSize: 11 }} domain={[0, "auto"]} />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
          labelStyle={{ color: "var(--color-text)" }}
        />
        <Line
          type="monotone"
          dataKey="best"
          stroke="var(--color-ok)"
          strokeWidth={2}
          dot={{ r: 3 }}
          name="best"
        />
        <Line
          type="monotone"
          dataKey="mean"
          stroke="var(--color-accent)"
          strokeWidth={1.5}
          dot={false}
          strokeDasharray="4 3"
          name="mean"
        />
        <Line
          type="monotone"
          dataKey="worst"
          stroke="var(--color-muted)"
          strokeWidth={1}
          dot={false}
          strokeDasharray="2 4"
          name="worst"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
