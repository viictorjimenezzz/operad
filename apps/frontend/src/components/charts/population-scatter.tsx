import { EmptyState } from "@/components/ui/empty-state";
import { FitnessEntry } from "@/lib/types";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

const FitnessRows = z.array(FitnessEntry);

interface PopulationScatterProps {
  data: unknown;
  height?: number;
}

interface Point {
  gen: number;
  score: number;
  isSurvivor: boolean;
}

export function PopulationScatter({ data, height = 220 }: PopulationScatterProps) {
  const parsed = FitnessRows.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no population data" />;
  }
  const points: Point[] = [];
  for (const row of parsed.data) {
    const sorted = [...row.population_scores].sort((a, b) => b - a);
    for (const score of row.population_scores) {
      // Approximate survivor rank: top half typically survives. The
      // exact survivor_indices live on the algo event itself, but we
      // don't have them in fitness.json — best vs mean placement is a
      // good visual proxy.
      const isSurvivor = sorted.indexOf(score) < Math.ceil(row.population_scores.length / 2);
      points.push({ gen: row.gen_index, score, isSurvivor });
    }
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis
          dataKey="gen"
          stroke="var(--color-muted)"
          tick={{ fontSize: 11 }}
          type="number"
          name="generation"
        />
        <YAxis
          dataKey="score"
          stroke="var(--color-muted)"
          tick={{ fontSize: 11 }}
          domain={[0, "auto"]}
        />
        <Tooltip
          cursor={{ stroke: "var(--color-border-strong)" }}
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        <Scatter data={points.filter((p) => p.isSurvivor)} fill="var(--color-ok)" />
        <Scatter data={points.filter((p) => !p.isSurvivor)} fill="var(--color-muted-2)" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
