import {
  type EvoIndividual,
  type EvoParameterDelta,
  buildEvoGenerations,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import {
  EmptyState,
  type RunFieldValue,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";

interface EvoParametersTabProps {
  summary?: unknown;
  fitness?: unknown;
  events?: unknown;
}

interface ParameterChange {
  id: string;
  generation: number;
  lineageId: string;
  individualId: number;
  score: number | null;
  scoreDelta: number | null;
  operator: string;
  delta: EvoParameterDelta;
}

const columns: RunTableColumn[] = [
  { id: "parameter", label: "Parameter", source: "parameter", sortable: true, width: "1fr" },
  { id: "type", label: "Type", source: "type", sortable: true, width: 124 },
  { id: "generation", label: "Gen", source: "generation", sortable: true, align: "right", width: 70 },
  { id: "score", label: "Score", source: "score", sortable: true, align: "right", width: 96 },
  { id: "delta", label: "Score delta", source: "delta", sortable: true, align: "right", width: 104 },
  { id: "operator", label: "Operator", source: "operator", sortable: true, width: 132 },
  { id: "change", label: "Change", source: "change", width: "1fr" },
  { id: "latest", label: "Latest selected value", source: "latest", width: "1fr" },
];

export function EvoParametersTab({ summary, fitness, events }: EvoParametersTabProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  const changes = selectedParameterChanges(generations);
  if (changes.length === 0) {
    return (
      <EmptyState
        title="no selected parameter changes"
        description="EvoGradient has not emitted parameter deltas for selected mutations"
      />
    );
  }
  const latestByParameter = new Map<string, ParameterChange>();
  for (const change of changes) latestByParameter.set(change.id, change);
  const rows = [...latestByParameter.values()]
    .sort((a, b) => a.id.localeCompare(b.id))
    .map(parameterRow);

  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={rows}
        columns={columns}
        storageKey="evogradient.parameters"
        pageSize={50}
        emptyTitle="no selected parameter changes"
        emptyDescription="selected mutations did not change trainable or mutated parameters"
      />
    </div>
  );
}

export function selectedParameterChanges(
  generations: Array<{
    genIndex: number;
    best: number | null;
    individuals: EvoIndividual[];
  }>,
): ParameterChange[] {
  const changes: ParameterChange[] = [];
  for (let index = 0; index < generations.length; index += 1) {
    const generation = generations[index];
    if (!generation) continue;
    const previousBest = index > 0 ? (generations[index - 1]?.best ?? null) : null;
    for (const individual of generation.individuals) {
      if (!individual.selected) continue;
      for (const delta of individual.parameterDeltas) {
        const id = `${delta.agentPath}.${delta.path}`;
        changes.push({
          id,
          generation: generation.genIndex,
          lineageId: individual.lineageId,
          individualId: individual.individualId,
          score: individual.score,
          scoreDelta:
            individual.score != null && previousBest != null ? individual.score - previousBest : null,
          operator: individual.op,
          delta,
        });
      }
    }
  }
  return changes;
}

function parameterRow(change: ParameterChange): RunRow {
  return {
    id: `${change.id}:${change.generation}:${change.lineageId}`,
    identity: change.id,
    state: "ended",
    startedAt: null,
    endedAt: null,
    durationMs: null,
    fields: {
      parameter: { kind: "text", value: change.id, mono: true },
      type: { kind: "text", value: change.delta.type, mono: true },
      generation: { kind: "num", value: change.generation, format: "int" },
      score: { kind: "score", value: change.score },
      delta: { kind: "num", value: change.scoreDelta, format: "score" },
      operator: { kind: "text", value: change.operator, mono: true },
      change: changeField(change.delta),
      latest: latestField(change.delta),
    },
  };
}

function changeField(delta: EvoParameterDelta): RunFieldValue {
  return {
    kind: "diff",
    previous: formatValue(delta.before),
    value: formatValue(delta.after),
  };
}

function latestField(delta: EvoParameterDelta): RunFieldValue {
  if (typeof delta.after === "number") return { kind: "param", value: delta.after, format: "number" };
  if (typeof delta.after === "string") return { kind: "param", value: delta.after, format: "text" };
  return { kind: "param", value: delta.after, format: "auto" };
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value == null) return "null";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
