import { Candidate } from "@/lib/types";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/shared/ui/empty-state";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

const CandidateArray = z.array(Candidate);

const NUM_BINS = 10;

function buildHistogram(scores: number[]): { bin: string; count: number }[] {
  if (scores.length === 0) return [];
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 1;
  const binSize = range / NUM_BINS;
  const bins: { bin: string; count: number }[] = Array.from({ length: NUM_BINS }, (_, i) => ({
    bin: (min + i * binSize).toFixed(2),
    count: 0,
  }));
  for (const s of scores) {
    const idx = Math.min(Math.floor((s - min) / binSize), NUM_BINS - 1);
    bins[idx]!.count++;
  }
  return bins;
}

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
  const histogram = buildHistogram(points.map((p) => p.score));

  return (
    <div className="flex flex-col gap-3">
      {/* Scatter */}
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

      {/* Score distribution histogram */}
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={histogram} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="bin" stroke="var(--color-muted)" tick={{ fontSize: 10 }} />
          <YAxis stroke="var(--color-muted)" tick={{ fontSize: 10 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "var(--color-bg-2)",
              border: "1px solid var(--color-border)",
              fontSize: 11,
            }}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {histogram.map((_, i) => (
              <Cell key={i} fill="var(--color-accent)" fillOpacity={0.7} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Top-K table with diff viewer */}
      <TopKDiffViewer sorted={sorted} />
    </div>
  );
}

function TopKDiffViewer({ sorted }: { sorted: { index: number; score: number }[] }) {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  function toggle(idx: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else if (next.size < 3) {
        next.add(idx);
      }
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="border-b border-border text-muted">
            <th className="px-2 py-1 text-left font-medium w-6" />
            <th className="px-2 py-1 text-left font-medium">rank</th>
            <th className="px-2 py-1 text-left font-medium">candidate</th>
            <th className="px-2 py-1 text-right font-medium">score</th>
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 5).map((p, i) => (
            <tr
              key={p.index}
              className={cn(
                "border-b border-border/60 cursor-pointer select-none",
                selected.has(p.index) && "bg-accent/10",
              )}
              onClick={() => toggle(p.index)}
            >
              <td className="px-2 py-1">
                <input
                  type="checkbox"
                  readOnly
                  checked={selected.has(p.index)}
                  className="pointer-events-none"
                />
              </td>
              <td className="px-2 py-1 font-mono">#{i + 1}</td>
              <td className="px-2 py-1 font-mono text-muted">candidate {p.index}</td>
              <td className="px-2 py-1 text-right font-mono tabular-nums text-text">
                {p.score.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected.size >= 2 && (
        <div className="flex gap-2 overflow-x-auto">
          {[...selected].map((idx) => (
            <div
              key={idx}
              className="flex-1 min-w-0 rounded border border-border bg-bg-2 p-2 text-[10px] font-mono text-muted"
            >
              <div className="mb-1 text-text font-medium">candidate {idx}</div>
              <span className="italic">— no text captured for this candidate —</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
