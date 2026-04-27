import {
  type EvoGeneration,
  buildEvoGenerations,
  numberValue,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import { MultiPromptDiff } from "@/components/charts/multi-prompt-diff";
import { EmptyState, PanelCard, Pill } from "@/components/ui";
import { formatNumber } from "@/lib/utils";
import { useSearchParams } from "react-router-dom";

interface EvoBestDiffTabProps {
  summary?: unknown;
  fitness?: unknown;
  events?: unknown;
}

export function EvoBestDiffTab({ summary, fitness, events }: EvoBestDiffTabProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  const [searchParams, setSearchParams] = useSearchParams();
  const rawGen = searchParams.get("gen");
  const requested = rawGen == null ? null : numberValue(Number(rawGen));
  const fallbackGen = generations.at(-1)?.genIndex ?? null;
  const selectedGen = requested ?? fallbackGen;
  const selected =
    selectedGen == null
      ? null
      : (generations.find((generation) => generation.genIndex === selectedGen) ?? null);
  const previous = selected
    ? (generations.filter((generation) => generation.genIndex < selected.genIndex).at(-1) ?? null)
    : null;

  if (!selected) {
    return (
      <EmptyState
        title="no best individual diff yet"
        description="select a generation after EvoGradient emits survivor data"
      />
    );
  }

  const delta =
    selected.best != null && previous?.best != null ? selected.best - previous.best : null;
  const prompts = [
    {
      runId: previous ? `gen-${previous.genIndex}` : "initial",
      label: previous ? `generation ${previous.genIndex}` : "initial",
      text: previous ? generationSnapshot(previous) : "initial agent state\n(no prior survivor)",
    },
    {
      runId: `gen-${selected.genIndex}`,
      label: `generation ${selected.genIndex}`,
      text: generationSnapshot(selected),
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-4">
      <PanelCard
        title={`generation ${selected.genIndex} best individual`}
        toolbar={
          <div className="flex items-center gap-2">
            {delta != null ? (
              <Pill tone={delta >= 0 ? "ok" : "warn"}>
                {delta >= 0 ? "+" : ""}
                {formatNumber(delta)}
              </Pill>
            ) : null}
            <select
              value={selected.genIndex}
              onChange={(event) => {
                const nextGen = event.currentTarget.value;
                setSearchParams(
                  (current) => {
                    const next = new URLSearchParams(current);
                    next.set("gen", nextGen);
                    return next;
                  },
                  { replace: true },
                );
              }}
              className="h-7 rounded border border-border bg-bg-2 px-2 text-[12px] text-text"
              aria-label="generation"
            >
              {generations.map((generation) => (
                <option key={generation.genIndex} value={generation.genIndex}>
                  gen {generation.genIndex}
                </option>
              ))}
            </select>
          </div>
        }
      >
        <div className="mb-3 grid gap-2 text-[12px] text-muted md:grid-cols-4">
          <Metric label="score" value={selected.best == null ? "-" : formatNumber(selected.best)} />
          <Metric
            label="previous"
            value={previous?.best == null ? "-" : formatNumber(previous.best)}
          />
          <Metric label="survivors" value={String(selected.survivorIndices.length)} />
          <Metric label="mutations" value={String(selected.mutations.length)} />
        </div>
        <MultiPromptDiff prompts={prompts} />
      </PanelCard>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-bg-2 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-[0.08em] text-muted-2">{label}</div>
      <div className="font-mono text-text">{value}</div>
    </div>
  );
}

function generationSnapshot(generation: EvoGeneration): string {
  const winner = bestSurvivorIndex(generation);
  const score = generation.scores[winner] ?? generation.best ?? null;
  const mutation = generation.mutations.find((candidate) => candidate.individualId === winner);
  const lines = [
    `generation: ${generation.genIndex}`,
    `best_survivor_index: ${winner}`,
    `score: ${score == null ? "-" : score.toFixed(4)}`,
    `operator: ${mutation?.op ?? "identity"}`,
    `path: ${mutation?.path || "root"}`,
    `improved: ${mutation ? String(mutation.improved) : "n/a"}`,
    "",
    "survivors:",
    ...generation.survivorIndices.map((index) => {
      const survivorMutation = generation.mutations.find(
        (candidate) => candidate.individualId === index,
      );
      const survivorScore = generation.scores[index];
      return [
        `- ${index}: score=${survivorScore == null ? "-" : survivorScore.toFixed(4)}`,
        `op=${survivorMutation?.op ?? "identity"}`,
        `path=${survivorMutation?.path || "root"}`,
      ].join(" ");
    }),
  ];
  return lines.join("\n");
}

function bestSurvivorIndex(generation: EvoGeneration): number {
  const candidates = generation.survivorIndices.length > 0 ? generation.survivorIndices : [0];
  return candidates.reduce((best, candidate) => {
    const bestScore = generation.scores[best] ?? Number.NEGATIVE_INFINITY;
    const candidateScore = generation.scores[candidate] ?? Number.NEGATIVE_INFINITY;
    return candidateScore > bestScore ? candidate : best;
  }, candidates[0] ?? 0);
}
