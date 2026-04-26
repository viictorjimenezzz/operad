import { EmptyState } from "@/shared/ui/empty-state";
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

interface IterationsResponse {
  iterations: { iter_index: number; score: number | null }[];
  threshold: number | null;
  converged: boolean | null;
}

function parseResponse(data: unknown): IterationsResponse | null {
  if (data == null || typeof data !== "object" || Array.isArray(data)) return null;
  const d = data as Record<string, unknown>;
  if (!Array.isArray(d.iterations)) return null;
  return {
    iterations: d.iterations
      .filter(
        (it): it is Record<string, unknown> => it != null && typeof it === "object",
      )
      .map((it) => ({
        iter_index: typeof it.iter_index === "number" ? it.iter_index : 0,
        score: typeof it.score === "number" ? it.score : null,
      })),
    threshold: typeof d.threshold === "number" ? d.threshold : null,
    converged: typeof d.converged === "boolean" ? d.converged : null,
  };
}

export function ConvergenceCurve({
  data,
  height = 220,
}: {
  data: unknown;
  height?: number;
}) {
  const resp = parseResponse(data);
  if (!resp || resp.iterations.length === 0) {
    return <EmptyState title="no iteration data" />;
  }

  const { iterations, threshold } = resp;

  const convergedIter =
    threshold != null
      ? iterations.find((p) => p.score != null && p.score >= threshold)?.iter_index
      : undefined;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={iterations} margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis
          dataKey="iter_index"
          stroke="var(--color-muted)"
          tick={{ fontSize: 11 }}
          label={{ value: "iteration", position: "insideBottom", offset: -4, fontSize: 11 }}
        />
        <YAxis
          dataKey="score"
          stroke="var(--color-muted)"
          tick={{ fontSize: 11 }}
          domain={[0, "auto"]}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        <Line
          type="monotone"
          dataKey="score"
          stroke="var(--color-accent)"
          strokeWidth={2}
          dot={{ r: 3, fill: "var(--color-accent)" }}
          connectNulls={false}
        />
        {threshold != null && (
          <ReferenceLine
            y={threshold}
            stroke="var(--color-ok)"
            strokeDasharray="4 4"
            label={{ value: "threshold", position: "right", fontSize: 10, fill: "var(--color-ok)" }}
          />
        )}
        {convergedIter != null && (
          <ReferenceLine
            x={convergedIter}
            stroke="var(--color-ok)"
            strokeDasharray="4 4"
            label={{ value: "converged", position: "top", fontSize: 10, fill: "var(--color-ok)" }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
