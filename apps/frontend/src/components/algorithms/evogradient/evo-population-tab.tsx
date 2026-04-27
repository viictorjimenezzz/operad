import {
  type EvoMutation,
  buildEvoGenerations,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import { EmptyState, PanelCard } from "@/components/ui";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface EvoPopulationTabProps {
  summary?: unknown;
  fitness?: unknown;
  events?: unknown;
}

interface PopulationPoint {
  individual: number;
  score: number;
  survivor: boolean;
  mutation: EvoMutation | null;
}

export function EvoPopulationTab({ summary, fitness, events }: EvoPopulationTabProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  const latestIndex = Math.max(0, generations.length - 1);
  const [selectedIndex, setSelectedIndex] = useState(latestIndex);
  const generation = generations[Math.min(selectedIndex, latestIndex)] ?? null;

  useEffect(() => {
    setSelectedIndex((current) => (current === 0 ? latestIndex : Math.min(current, latestIndex)));
  }, [latestIndex]);

  const points = useMemo(() => {
    if (!generation) return [];
    return generation.scores.map((score, individual) => ({
      individual,
      score,
      survivor: generation.survivorIndices.includes(individual),
      mutation:
        generation.mutations.find((candidate) => candidate.individualId === individual) ?? null,
    }));
  }, [generation]);

  if (generations.length === 0 || !generation) {
    return (
      <EmptyState
        title="no population data"
        description="EvoGradient has not emitted a population snapshot for this run"
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <PanelCard title="generation scrubber">
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={latestIndex}
            value={Math.min(selectedIndex, latestIndex)}
            onChange={(event) => setSelectedIndex(Number(event.currentTarget.value))}
            className="w-full accent-[--color-accent]"
            aria-label="generation"
          />
          <span className="w-20 text-right font-mono text-[12px] text-text">
            gen {generation.genIndex}
          </span>
        </div>
      </PanelCard>

      <PanelCard title="population snapshot" bodyMinHeight={390}>
        <ResponsiveContainer width="100%" height={360}>
          <ScatterChart margin={{ top: 14, right: 18, bottom: 10, left: 0 }}>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
            <XAxis
              dataKey="individual"
              type="number"
              stroke="var(--color-muted)"
              tick={{ fontSize: 11 }}
              name="individual"
              allowDecimals={false}
            />
            <YAxis
              dataKey="score"
              type="number"
              stroke="var(--color-muted)"
              tick={{ fontSize: 11 }}
              name="score"
              domain={[0, "auto"]}
            />
            <Tooltip
              cursor={{ stroke: "var(--color-border-strong)" }}
              content={<PopulationTooltip />}
            />
            <Scatter
              name="survivors"
              data={points.filter((point) => point.survivor)}
              fill="var(--color-ok)"
              shape="circle"
            />
            <Scatter
              name="eliminated"
              data={points.filter((point) => !point.survivor)}
              fill="var(--color-bg-1)"
              stroke="var(--color-muted)"
              shape="circle"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </PanelCard>

      <PanelCard title="mutations this generation">
        <div className="grid gap-2 md:grid-cols-2">
          {points.map((point) => (
            <div
              key={point.individual}
              className="rounded-md border border-border bg-bg-2 p-2 text-[12px]"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-text">individual {point.individual}</span>
                <span className={point.survivor ? "text-[--color-ok]" : "text-muted"}>
                  {point.survivor ? "survivor" : "eliminated"}
                </span>
              </div>
              <div className="mt-1 font-mono text-[11px] text-muted">
                {point.mutation ? mutationLabel(point.mutation) : "no mutation recorded"}
              </div>
            </div>
          ))}
        </div>
      </PanelCard>
    </div>
  );
}

function PopulationTooltip({ active, payload }: { active?: boolean; payload?: unknown[] }) {
  if (!active || !Array.isArray(payload)) return null;
  const point = payload[0] as { payload?: PopulationPoint } | undefined;
  const data = point?.payload;
  if (!data) return null;
  return (
    <div className="rounded border border-border bg-bg-2 p-2 text-[11px] shadow-[var(--shadow-popover)]">
      <div className="font-mono text-text">individual {data.individual}</div>
      <div className="text-muted">score {data.score.toFixed(3)}</div>
      <div className={data.survivor ? "text-[--color-ok]" : "text-muted"}>
        {data.survivor ? "survivor" : "eliminated"}
      </div>
      <div className="mt-1 max-w-56 font-mono text-muted">
        {data.mutation ? mutationLabel(data.mutation) : "no mutation recorded"}
      </div>
    </div>
  );
}

function mutationLabel(mutation: EvoMutation): string {
  const path = mutation.path ? `(${mutation.path})` : "";
  const improved = mutation.improved ? "improved" : "no gain";
  return `${mutation.op}${path} - ${improved}`;
}
