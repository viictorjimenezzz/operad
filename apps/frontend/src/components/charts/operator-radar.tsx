import { EmptyState } from "@/components/ui/empty-state";
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

export interface OperatorRadarRun {
  runId: string;
  label: string;
  operatorRates: Record<string, number>;
}

interface OperatorRadarProps {
  runs: OperatorRadarRun[];
  height?: number;
}

const COLORS = [
  "var(--color-accent)",
  "var(--color-ok)",
  "var(--color-warn)",
  "var(--color-err)",
  "var(--color-chunk)",
];

export function OperatorRadar({ runs, height = 260 }: OperatorRadarProps) {
  const withOps = runs.filter((r) => Object.keys(r.operatorRates).length > 0);
  if (withOps.length === 0) {
    return <EmptyState title="no mutation operator data" />;
  }

  const operators = [...new Set(withOps.flatMap((r) => Object.keys(r.operatorRates)))].sort();
  if (operators.length === 0) {
    return <EmptyState title="no mutation operator data" />;
  }

  const data = operators.map((operator) => {
    const row: Record<string, number | string> = { operator };
    for (const run of withOps) {
      row[`run:${run.runId}`] = run.operatorRates[operator] ?? 0;
    }
    return row;
  });

  return (
    <div className="flex h-full w-full items-center justify-center" style={{ minHeight: height }}>
      <ResponsiveContainer width="100%" height={height}>
      <RadarChart
        data={data}
        outerRadius="68%"
        margin={{ top: 18, right: 54, bottom: 18, left: 54 }}
      >
        <PolarGrid stroke="var(--color-border)" />
        <PolarAngleAxis dataKey="operator" tick={{ fill: "var(--color-muted)", fontSize: 10 }} />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
          formatter={(v: number) => `${(v * 100).toFixed(0)}%`}
        />
        <Legend verticalAlign="bottom" height={24} />
        {withOps.map((run, i) => (
          <Radar
            key={run.runId}
            name={run.label}
            dataKey={`run:${run.runId}`}
            stroke={COLORS[i % COLORS.length]}
            fill={COLORS[i % COLORS.length]}
            fillOpacity={0.2}
          />
        ))}
      </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
