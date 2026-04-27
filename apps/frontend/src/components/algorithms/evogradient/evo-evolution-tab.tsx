import {
  type EvoGeneration,
  buildEvoGenerations,
  numberValue,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import { EmptyState, PanelCard } from "@/components/ui";
import { formatNumber } from "@/lib/utils";
import { useSearchParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface EvoEvolutionTabProps {
  summary?: unknown;
  fitness?: unknown;
  events?: unknown;
}

type EvolutionRow = Record<string, number | [number, number] | null>;

export function EvoEvolutionTab({ summary, fitness, events }: EvoEvolutionTabProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  const [, setSearchParams] = useSearchParams();

  if (generations.length === 0) {
    return (
      <EmptyState
        title="no generations recorded yet"
        description="the first EvoGradient generation event will populate this chart"
      />
    );
  }

  const rows = generations.map(evolutionRow);
  const maxPopulation = generations.reduce((max, gen) => Math.max(max, gen.scores.length), 0);
  const survivorSlots = new Set(generations.flatMap((gen) => gen.survivorIndices));

  const pinGeneration = (state: unknown) => {
    const activePayload = Array.isArray((state as { activePayload?: unknown }).activePayload)
      ? ((state as { activePayload?: Array<{ payload?: EvolutionRow }> }).activePayload ?? [])
      : [];
    const gen = numberValue(activePayload[0]?.payload?.gen);
    if (gen == null) return;
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("tab", "best-diff");
        next.set("gen", String(gen));
        return next;
      },
      { replace: false },
    );
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <PanelCard title="fitness over generations" bodyMinHeight={390}>
        <ResponsiveContainer width="100%" height={360}>
          <AreaChart
            data={rows}
            margin={{ top: 14, right: 18, bottom: 10, left: 0 }}
            onClick={pinGeneration}
          >
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
            <XAxis
              dataKey="gen"
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
              formatter={(value: number | [number, number]) =>
                Array.isArray(value)
                  ? `${formatNumber(value[0])} - ${formatNumber(value[1])}`
                  : formatNumber(value)
              }
            />
            <Area
              type="monotone"
              dataKey="spread"
              name="worst-best spread"
              stroke="transparent"
              fill="var(--color-accent)"
              fillOpacity={0.12}
              activeDot={false}
            />
            <Line
              type="monotone"
              dataKey="best"
              name="best"
              stroke="var(--color-ok)"
              strokeWidth={2.2}
              dot={{ r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="mean"
              name="mean"
              stroke="var(--color-accent)"
              strokeWidth={1.6}
              strokeDasharray="4 3"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="worst"
              name="worst"
              stroke="var(--color-muted)"
              strokeWidth={1}
              strokeDasharray="2 4"
              dot={false}
            />
            {Array.from({ length: maxPopulation }, (_, index) => (
              <Line
                key={index}
                type="linear"
                dataKey={`slot${index}`}
                name={`individual ${index}`}
                stroke={survivorSlots.has(index) ? "var(--qual-7)" : "var(--color-muted-2)"}
                strokeOpacity={survivorSlots.has(index) ? 0.42 : 0.18}
                strokeWidth={survivorSlots.has(index) ? 1.6 : 0.9}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </PanelCard>

      <PanelCard title="population paths">
        <div className="grid gap-2 text-[12px] text-muted md:grid-cols-3">
          {generations.slice(-6).map((gen) => (
            <GenerationStrip key={gen.genIndex} generation={gen} />
          ))}
        </div>
      </PanelCard>
    </div>
  );
}

function evolutionRow(generation: EvoGeneration): EvolutionRow {
  const worst = generation.worst ?? null;
  const best = generation.best ?? null;
  const row: EvolutionRow = {
    gen: generation.genIndex,
    best,
    mean: generation.mean,
    worst,
    spread: worst != null && best != null ? [worst, best] : null,
  };
  generation.scores.forEach((score, index) => {
    row[`slot${index}`] = score;
  });
  return row;
}

function GenerationStrip({ generation }: { generation: EvoGeneration }) {
  const sorted = [...generation.scores].sort((a, b) => a - b);
  return (
    <button
      type="button"
      className="rounded-md border border-border bg-bg-2 p-2 text-left transition-colors hover:border-border-strong"
      title={`generation ${generation.genIndex}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-mono text-text">gen {generation.genIndex}</span>
        <span>{generation.survivorIndices.length} survivors</span>
      </div>
      <div className="flex h-8 items-end gap-1">
        {sorted.map((score, index) => (
          <span
            key={`${generation.genIndex}-${index}`}
            className="w-full rounded-t bg-[--color-accent-dim]"
            style={{ height: `${Math.max(8, Math.min(32, score * 32))}px` }}
          />
        ))}
      </div>
    </button>
  );
}
