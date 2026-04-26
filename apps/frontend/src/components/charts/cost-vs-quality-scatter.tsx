import { EmptyState } from "@/components/ui/empty-state";
import {
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface CostQualityPoint {
  runId: string;
  label: string;
  cost: number;
  quality: number;
}

interface CostVsQualityScatterProps {
  points: CostQualityPoint[];
  paretoRunIds: string[];
  height?: number;
}

export function CostVsQualityScatter({
  points,
  paretoRunIds,
  height = 260,
}: CostVsQualityScatterProps) {
  if (points.length === 0) {
    return <EmptyState title="no cost/quality data" />;
  }

  const paretoSet = new Set(paretoRunIds);
  const frontier = points
    .filter((p) => paretoSet.has(p.runId))
    .sort((a, b) => a.cost - b.cost || a.quality - b.quality);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 12, right: 20, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="cost"
          name="cost"
          stroke="var(--color-muted)"
          tick={{ fontSize: 11 }}
          label={{ value: "cost", position: "insideBottomRight", offset: -2, fontSize: 10 }}
        />
        <YAxis
          type="number"
          dataKey="quality"
          name="quality"
          stroke="var(--color-muted)"
          tick={{ fontSize: 11 }}
          label={{ value: "quality", angle: -90, position: "insideLeft", fontSize: 10 }}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
          formatter={(v: number, name: string) => [v.toFixed(3), name]}
        />

        <Scatter data={points} fill="var(--color-accent)">
          <LabelList dataKey="label" position="top" fontSize={10} fill="var(--color-muted)" />
        </Scatter>

        {frontier.length > 1 ? (
          <Scatter
            data={frontier}
            line={{ stroke: "var(--color-ok)", strokeWidth: 2 }}
            fill="var(--color-ok)"
          />
        ) : null}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
