import { Candidate } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
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

const CandidateArray = z.array(Candidate);

export function BeamCandidateChart({ data, height = 220 }: { data: unknown; height?: number }) {
  const parsed = CandidateArray.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no beam candidates" />;
  }
  const points = parsed.data
    .filter((c) => c.candidate_index != null && c.score != null)
    .map((c) => ({ index: c.candidate_index as number, score: c.score as number }));
  const sorted = [...points].sort((a, b) => b.score - a.score);
  const topK = new Set(sorted.slice(0, Math.min(3, sorted.length)).map((p) => p.index));

  const top = points.filter((p) => topK.has(p.index));
  const rest = points.filter((p) => !topK.has(p.index));

  return (
    <div className="flex flex-col gap-3">
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="index"
            stroke="var(--color-muted)"
            tick={{ fontSize: 11 }}
            type="number"
            name="candidate"
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
          <Scatter data={rest} fill="var(--color-muted-2)" />
          <Scatter data={top} fill="var(--color-ok)" />
        </ScatterChart>
      </ResponsiveContainer>

      <table className="w-full text-[11px]">
        <thead>
          <tr className="border-b border-border text-muted">
            <th className="px-2 py-1 text-left font-medium">rank</th>
            <th className="px-2 py-1 text-left font-medium">candidate</th>
            <th className="px-2 py-1 text-right font-medium">score</th>
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 5).map((p, i) => (
            <tr key={p.index} className="border-b border-border/60">
              <td className="px-2 py-1 font-mono">#{i + 1}</td>
              <td className="px-2 py-1 font-mono text-muted">candidate {p.index}</td>
              <td className="px-2 py-1 text-right font-mono tabular-nums text-text">
                {p.score.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
