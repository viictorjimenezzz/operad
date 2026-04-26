import { Candidate } from "@/lib/types";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/shared/ui/empty-state";
import { useMemo, useState } from "react";
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

const IterationsResponse = z.object({
  iterations: z
    .array(
      z.object({
        iter_index: z.number(),
        phase: z.string().nullable(),
        metadata: z.record(z.unknown()).default({}),
      }),
    )
    .default([]),
});

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

function asIndexList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter((x): x is number => typeof x === "number");
}

interface CandidatePoint {
  index: number;
  score: number;
  text: string | null;
}

export function BeamCandidateChart({
  data,
  iterationsData,
  height = 220,
}: {
  data: unknown;
  iterationsData?: unknown;
  height?: number;
}) {
  const parsed = CandidateArray.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no beam candidates" />;
  }

  const points: CandidatePoint[] = parsed.data
    .filter((c) => c.candidate_index != null && c.score != null)
    .map((c) => ({
      index: c.candidate_index as number,
      score: c.score as number,
      text: c.text,
    }));

  if (points.length === 0) {
    return <EmptyState title="no beam candidates" />;
  }

  const sorted = [...points].sort((a, b) => b.score - a.score);
  const topK = new Set(sorted.slice(0, Math.min(3, sorted.length)).map((p) => p.index));

  const top = points.filter((p) => topK.has(p.index));
  const rest = points.filter((p) => !topK.has(p.index));
  const histogram = buildHistogram(points.map((p) => p.score));

  const pruneSteps = useMemo(() => {
    const it = IterationsResponse.safeParse(iterationsData);
    if (!it.success) return [];
    return it.data.iterations
      .filter((row) => row.phase === "prune")
      .map((row) => ({
        iterIndex: row.iter_index,
        kept: asIndexList(row.metadata.top_indices),
        dropped: asIndexList(row.metadata.dropped_indices),
      }));
  }, [iterationsData]);

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

      <TopKDiffViewer sorted={sorted} />
      <PruningView steps={pruneSteps} />
    </div>
  );
}

function TopKDiffViewer({ sorted }: { sorted: CandidatePoint[] }) {
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

  const byIndex = new Map(sorted.map((s) => [s.index, s]));

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
          {[...selected].map((idx) => {
            const row = byIndex.get(idx);
            return (
              <div
                key={idx}
                className="flex-1 min-w-0 rounded border border-border bg-bg-2 p-2 text-[10px] font-mono text-muted"
              >
                <div className="mb-1 text-text font-medium">candidate {idx}</div>
                <p className="whitespace-pre-wrap break-words text-text/80">
                  {row?.text && row.text.length > 0 ? row.text : "(empty candidate text)"}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PruningView({
  steps,
}: {
  steps: Array<{ iterIndex: number; kept: number[]; dropped: number[] }>;
}) {
  if (steps.length === 0) {
    return <div className="text-[11px] text-muted">no pruning steps captured</div>;
  }

  return (
    <div className="rounded border border-border/70 bg-bg-2 p-2">
      <div className="mb-2 text-[11px] font-medium text-text">pruning by iteration</div>
      <ul className="flex flex-col gap-1 text-[11px]">
        {steps.map((step) => (
          <li key={step.iterIndex} className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-muted">#{step.iterIndex}</span>
            <span className="rounded px-1.5 py-0.5 bg-green-500/15 text-green-400">
              kept [{step.kept.join(", ")}]
            </span>
            <span className="rounded px-1.5 py-0.5 bg-rose-500/15 text-rose-400">
              dropped [{step.dropped.join(", ")}]
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
