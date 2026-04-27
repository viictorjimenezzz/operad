import { FitnessCurve } from "@/components/charts/fitness-curve";
import { OperatorRadar, type OperatorRadarRun } from "@/components/charts/operator-radar";
import { EmptyState, PanelCard, PanelGrid, Pill, StatTile } from "@/components/ui";
import { formatCost, formatDurationMs, formatNumber, formatTokens } from "@/lib/utils";

export interface EvoMutation {
  individualId: number;
  op: string;
  path: string;
  improved: boolean;
}

export interface EvoGeneration {
  genIndex: number;
  scores: number[];
  best: number | null;
  mean: number | null;
  worst: number | null;
  survivorIndices: number[];
  mutations: EvoMutation[];
  opAttempts: Record<string, number>;
  opSuccess: Record<string, number>;
  timestamp: number | null;
}

interface EvoDetailOverviewProps {
  summary?: unknown;
  fitness?: unknown;
  mutations?: unknown;
  events?: unknown;
}

export function EvoDetailOverview({ summary, fitness, mutations, events }: EvoDetailOverviewProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  const latest = generations.at(-1) ?? null;
  const summaryRecord = asRecord(summary);
  const startPayload = findAlgoStartPayload(events);
  const populationSize =
    numberValue(startPayload?.population_size) ?? latest?.scores.length ?? null;
  const totalAttempts = generations.reduce(
    (sum, gen) => sum + Object.values(gen.opAttempts).reduce((a, b) => a + b, 0),
    0,
  );
  const totalSuccess = generations.reduce(
    (sum, gen) => sum + Object.values(gen.opSuccess).reduce((a, b) => a + b, 0),
    0,
  );
  const survivorAverage =
    generations.length > 0
      ? generations.reduce((sum, gen) => sum + gen.survivorIndices.length, 0) / generations.length
      : null;
  const durationMs = numberValue(summaryRecord?.duration_ms);
  const cost = numberValue(asRecord(summaryRecord?.cost)?.cost_usd);
  const promptTokens = numberValue(summaryRecord?.prompt_tokens) ?? 0;
  const completionTokens = numberValue(summaryRecord?.completion_tokens) ?? 0;
  const state = stringValue(summaryRecord?.state) ?? "running";
  const statusTone = state === "error" ? "error" : state === "running" ? "live" : "ok";
  const radarRuns = operatorRadarRuns(mutations, stringValue(summaryRecord?.run_id) ?? "run");

  if (!summaryRecord && generations.length === 0) {
    return (
      <EmptyState
        title="evogradient data unavailable"
        description="the dashboard has not loaded this optimizer run yet"
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-bg-1 px-3 py-2 text-[12px] text-muted">
        <Pill tone={statusTone} pulse={state === "running"}>
          {state}
        </Pill>
        <span className="font-mono text-text">gen {latest ? latest.genIndex + 1 : 0}</span>
        <span>pop {populationSize ?? "-"}</span>
        <span>best {latest?.best != null ? formatNumber(latest.best) : "-"}</span>
        <span>cost {formatCost(cost)}</span>
        <span>tokens {formatTokens(promptTokens + completionTokens)}</span>
      </div>

      <PanelGrid cols={2} gap="md">
        <PanelCard title="fitness spread" bodyMinHeight={280}>
          <FitnessCurve data={fitness} height={250} />
        </PanelCard>
        <PanelCard title="operator success" bodyMinHeight={280}>
          <OperatorRadar runs={radarRuns} height={250} />
        </PanelCard>
      </PanelGrid>

      <PanelGrid cols={3} gap="md">
        <PanelCard surface="inset" bare>
          <StatTile label="population size" value={populationSize ?? "-"} size="sm" />
        </PanelCard>
        <PanelCard surface="inset" bare>
          <StatTile label="generations" value={generations.length} size="sm" />
        </PanelCard>
        <PanelCard surface="inset" bare>
          <StatTile
            label="survivors per gen"
            value={survivorAverage == null ? "-" : survivorAverage.toFixed(1)}
            size="sm"
          />
        </PanelCard>
        <PanelCard surface="inset" bare>
          <StatTile label="ops attempted" value={totalAttempts} size="sm" />
        </PanelCard>
        <PanelCard surface="inset" bare>
          <StatTile label="ops succeeded" value={totalSuccess} size="sm" />
        </PanelCard>
        <PanelCard surface="inset" bare>
          <StatTile label="wall time" value={formatDurationMs(durationMs)} size="sm" />
        </PanelCard>
      </PanelGrid>
    </div>
  );
}

export function buildEvoGenerations(
  summary: unknown,
  fitness: unknown,
  events: unknown,
): EvoGeneration[] {
  const byGen = new Map<number, EvoGeneration>();

  for (const row of arrayValue(fitness)) {
    const record = asRecord(row);
    const genIndex = numberValue(record?.gen_index);
    if (genIndex == null) continue;
    const scores = numberArray(record?.population_scores);
    upsertGeneration(byGen, genIndex, {
      scores,
      best: numberValue(record?.best),
      mean: numberValue(record?.mean),
      worst: numberValue(record?.worst),
      timestamp: numberValue(record?.timestamp),
    });
  }

  for (const row of arrayValue(asRecord(summary)?.generations)) {
    const record = asRecord(row);
    const genIndex = numberValue(record?.gen_index);
    if (genIndex == null) continue;
    const scores = numberArray(record?.scores);
    upsertGeneration(byGen, genIndex, {
      scores,
      best: numberValue(record?.best),
      mean: numberValue(record?.mean),
      worst: scores.length > 0 ? Math.min(...scores) : null,
      survivorIndices: numberArray(record?.survivor_indices),
      opAttempts: numberRecord(record?.op_attempt_counts),
      opSuccess: numberRecord(record?.op_success_counts),
      timestamp: numberValue(record?.timestamp),
    });
  }

  for (const payload of generationPayloads(events)) {
    const genIndex = numberValue(payload.gen_index);
    if (genIndex == null) continue;
    const scores = numberArray(payload.population_scores);
    upsertGeneration(byGen, genIndex, {
      scores,
      best: scores.length > 0 ? Math.max(...scores) : null,
      mean: scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null,
      worst: scores.length > 0 ? Math.min(...scores) : null,
      survivorIndices: numberArray(payload.survivor_indices),
      mutations: mutationArray(payload.mutations),
      opAttempts: numberRecord(payload.op_attempt_counts),
      opSuccess: numberRecord(payload.op_success_counts),
    });
  }

  return [...byGen.values()].sort((a, b) => a.genIndex - b.genIndex);
}

export function generationPayloads(events: unknown): Record<string, unknown>[] {
  return arrayValue(asRecord(events)?.events)
    .map(asRecord)
    .filter(
      (event): event is Record<string, unknown> =>
        event?.type === "algo_event" && event.kind === "generation",
    )
    .map((event) => asRecord(event.payload))
    .filter((payload): payload is Record<string, unknown> => payload != null);
}

export function findAlgoStartPayload(events: unknown): Record<string, unknown> | null {
  const event = arrayValue(asRecord(events)?.events)
    .map(asRecord)
    .find((candidate) => candidate?.type === "algo_event" && candidate.kind === "algo_start");
  return asRecord(event?.payload);
}

export function operatorRadarRuns(mutations: unknown, runId: string): OperatorRadarRun[] {
  const matrix = asRecord(mutations);
  const ops = stringArray(matrix?.ops);
  const attempts = matrixArray(matrix?.attempts);
  const success = matrixArray(matrix?.success);
  const operatorRates: Record<string, number> = {};
  ops.forEach((op, index) => {
    const totalAttempts = attempts[index]?.reduce((sum, value) => sum + value, 0) ?? 0;
    const totalSuccess = success[index]?.reduce((sum, value) => sum + value, 0) ?? 0;
    operatorRates[op] = totalAttempts > 0 ? totalSuccess / totalAttempts : 0;
  });
  return [{ runId, label: "success rate", operatorRates }];
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function numberArray(value: unknown): number[] {
  return Array.isArray(value)
    ? value.filter((item): item is number => typeof item === "number" && Number.isFinite(item))
    : [];
}

export function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

export function numberRecord(value: unknown): Record<string, number> {
  const record = asRecord(value);
  if (!record) return {};
  const out: Record<string, number> = {};
  for (const [key, item] of Object.entries(record)) {
    const number = numberValue(item);
    if (number != null) out[key] = number;
  }
  return out;
}

function upsertGeneration(
  byGen: Map<number, EvoGeneration>,
  genIndex: number,
  patch: Partial<Omit<EvoGeneration, "genIndex">>,
) {
  const existing = byGen.get(genIndex);
  const next: EvoGeneration = {
    genIndex,
    scores: patch.scores ?? existing?.scores ?? [],
    best: patch.best ?? existing?.best ?? null,
    mean: patch.mean ?? existing?.mean ?? null,
    worst: patch.worst ?? existing?.worst ?? null,
    survivorIndices: patch.survivorIndices ?? existing?.survivorIndices ?? [],
    mutations: patch.mutations ?? existing?.mutations ?? [],
    opAttempts: patch.opAttempts ?? existing?.opAttempts ?? {},
    opSuccess: patch.opSuccess ?? existing?.opSuccess ?? {},
    timestamp: patch.timestamp ?? existing?.timestamp ?? null,
  };
  byGen.set(genIndex, next);
}

function mutationArray(value: unknown): EvoMutation[] {
  return arrayValue(value)
    .map(asRecord)
    .flatMap((record) => {
      const individualId = numberValue(record?.individual_id);
      const op = stringValue(record?.op);
      if (individualId == null || op == null) return [];
      return [
        {
          individualId,
          op,
          path: stringValue(record?.path) ?? "",
          improved: Boolean(record?.improved),
        },
      ];
    });
}

function matrixArray(value: unknown): number[][] {
  return Array.isArray(value) ? value.map(numberArray) : [];
}
