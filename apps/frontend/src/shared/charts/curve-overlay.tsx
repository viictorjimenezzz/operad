import { EmptyState } from "@/shared/ui/empty-state";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface CurveOverlaySeries {
  runId: string;
  label: string;
  points: Array<{ x: number; y: number }>;
}

interface CurveOverlayProps {
  series: CurveOverlaySeries[];
  isHeterogeneous?: boolean;
  height?: number;
}

export function normalizeSeriesForComparison(
  points: Array<{ x: number; y: number }>,
  isHeterogeneous: boolean,
): Array<{ x: number; y: number }> {
  if (!isHeterogeneous) return points;
  return points.map((p, i) => ({ x: i, y: p.y }));
}

const COLORS = [
  "var(--color-accent)",
  "var(--color-ok)",
  "var(--color-warn)",
  "var(--color-err)",
  "var(--color-chunk)",
];

export function CurveOverlay({
  series,
  isHeterogeneous = false,
  height = 280,
}: CurveOverlayProps) {
  const nonEmpty = series.filter((s) => s.points.length > 0);
  if (nonEmpty.length === 0) {
    return <EmptyState title="no curve data" description="selected runs have no comparable curve" />;
  }

  const rows = new Map<number, Record<string, number | null>>();

  for (const s of nonEmpty) {
    const key = `series:${s.runId}`;
    const points = normalizeSeriesForComparison(s.points, isHeterogeneous);
    for (const p of points) {
      const row = rows.get(p.x) ?? { x: p.x };
      row[key] = p.y;
      rows.set(p.x, row);
    }
  }

  const data = [...rows.values()].sort((a, b) => (a.x as number) - (b.x as number));

  return (
    <div>
      {isHeterogeneous ? (
        <div className="mb-2 text-[11px] text-muted">primary metric (varies)</div>
      ) : null}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="x"
            stroke="var(--color-muted)"
            tick={{ fontSize: 11 }}
            label={{
              value: isHeterogeneous ? "step index" : "step",
              position: "insideBottomRight",
              offset: -2,
              style: { fill: "var(--color-muted)", fontSize: 10 },
            }}
          />
          <YAxis
            stroke="var(--color-muted)"
            tick={{ fontSize: 11 }}
            {...(isHeterogeneous
              ? {
                  label: {
                    value: "primary metric (varies)",
                    angle: -90,
                    position: "insideLeft",
                    style: { fill: "var(--color-muted)", fontSize: 10 },
                  },
                }
              : {})}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-bg-2)",
              border: "1px solid var(--color-border)",
              fontSize: 11,
            }}
          />
          <Legend />
          {nonEmpty.map((s, i) => (
            <Line
              key={s.runId}
              type="monotone"
              dataKey={`series:${s.runId}`}
              name={s.label}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
