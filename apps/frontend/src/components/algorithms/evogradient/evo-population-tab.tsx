import {
  asRecord,
  type EvoGeneration,
  type EvoIndividual,
  type EvoParameterDelta,
  buildEvoGenerations,
  numberValue,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import {
  EmptyState,
  PanelCard,
  type RunFieldValue,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";
import { formatNumber } from "@/lib/utils";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
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
  individualId: number;
  lineageId: string;
  score: number;
  selected: boolean;
  active: boolean;
  op: string;
  path: string;
  diff: string;
}

const columns: RunTableColumn[] = [
  { id: "focus", label: "", source: "focus", width: 70 },
  { id: "individual", label: "Individual", source: "individual", sortable: true, width: 94 },
  { id: "lineage", label: "Lineage", source: "lineage", sortable: true, width: 104 },
  { id: "parent", label: "Parent", source: "parent", sortable: true, width: 104 },
  { id: "score", label: "Score", source: "score", sortable: true, align: "right", width: 110 },
  { id: "operator", label: "Operator", source: "operator", sortable: true, width: 132 },
  { id: "path", label: "Path", source: "path", sortable: true, width: 140 },
  { id: "diff", label: "Parameter diff", source: "diff", width: "1fr" },
];

export function EvoPopulationTab({ summary, fitness, events }: EvoPopulationTabProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedGen = parseParamNumber(searchParams.get("gen"));
  const requestedIndividual = parseParamNumber(searchParams.get("individual"));
  const generation =
    generations.find((candidate) => candidate.genIndex === requestedGen) ?? generations.at(-1) ?? null;
  const activeIndividual =
    requestedIndividual ??
    generation?.individuals.find((individual) => generation.selectedLineageId === individual.lineageId)
      ?.individualId ??
    generation?.survivorIndices[0] ??
    0;

  const points = useMemo(
    () =>
      generationIndividuals(generation).flatMap((individual) =>
        individual.score == null
          ? []
          : [
              {
                individualId: individual.individualId,
                lineageId: individual.lineageId,
                score: individual.score,
                selected: individual.selected,
                active: individual.individualId === activeIndividual,
                op: individual.op,
                path: individual.path,
                diff: deltaSummary(individual.parameterDeltas),
              },
            ],
      ),
    [activeIndividual, generation],
  );

  const scoreBounds = useMemo(() => {
    const scores = points.map((point) => point.score);
    return {
      min: scores.length > 0 ? Math.min(...scores) : 0,
      max: scores.length > 0 ? Math.max(...scores) : 1,
    };
  }, [points]);

  const rows = useMemo(
    () =>
      generationIndividuals(generation).map((individual) =>
        individualRow(individual, activeIndividual, scoreBounds.min, scoreBounds.max),
      ),
    [activeIndividual, generation, scoreBounds.max, scoreBounds.min],
  );

  if (generations.length === 0 || !generation) {
    return (
      <EmptyState
        title="no population data"
        description="EvoGradient has not emitted a population snapshot for this run"
      />
    );
  }

  const selectGeneration = (genIndex: number) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("gen", String(genIndex));
        next.delete("individual");
        return next;
      },
      { replace: false },
    );
  };
  const selectIndividual = (individualId: number) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("gen", String(generation.genIndex));
        next.set("individual", String(individualId));
        return next;
      },
      { replace: false },
    );
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <PanelCard title="generation">
        <div className="flex flex-wrap items-center gap-2">
          {generations.length <= 10 ? (
            generations.map((item) => (
              <button
                key={item.genIndex}
                type="button"
                onClick={() => selectGeneration(item.genIndex)}
                className={
                  item.genIndex === generation.genIndex
                    ? "h-7 rounded border border-accent bg-accent px-2 font-mono text-[12px] text-bg"
                    : "h-7 rounded border border-border bg-bg-2 px-2 font-mono text-[12px] text-muted transition-colors hover:border-border-strong hover:text-text"
                }
              >
                gen {item.genIndex}
              </button>
            ))
          ) : (
            <select
              value={generation.genIndex}
              onChange={(event) => selectGeneration(Number(event.currentTarget.value))}
              className="h-7 rounded border border-border bg-bg-2 px-2 text-[12px] text-text"
              aria-label="generation"
            >
              {generations.map((item) => (
                <option key={item.genIndex} value={item.genIndex}>
                  gen {item.genIndex}
                </option>
              ))}
            </select>
          )}
          <span className="ml-auto font-mono text-[12px] text-muted">
            {generation.individuals.filter((individual) => individual.selected).length} selected /{" "}
            {generationIndividuals(generation).length} individuals
          </span>
        </div>
      </PanelCard>

      <PanelCard title="population snapshot" bodyMinHeight={390}>
        <ResponsiveContainer width="100%" height={360}>
          <ScatterChart margin={{ top: 16, right: 28, bottom: 18, left: 6 }}>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
            <XAxis
              dataKey="individualId"
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
              domain={["auto", "auto"]}
            />
            <Tooltip cursor={{ stroke: "var(--color-border-strong)" }} content={<PopulationTooltip />} />
            <Scatter
              name="discarded"
              data={points.filter((point) => !point.selected && !point.active)}
              fill="var(--color-bg-1)"
              stroke="var(--color-muted)"
              onClick={(point) => selectIndividualFromPoint(point, selectIndividual)}
            />
            <Scatter
              name="selected"
              data={points.filter((point) => point.selected && !point.active)}
              fill="var(--color-ok)"
              onClick={(point) => selectIndividualFromPoint(point, selectIndividual)}
            />
            <Scatter
              name="active"
              data={points.filter((point) => point.active)}
              fill="var(--color-accent)"
              stroke="var(--color-text)"
              onClick={(point) => selectIndividualFromPoint(point, selectIndividual)}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </PanelCard>

      <PanelCard title="mutations this generation">
        <RunTable
          rows={rows}
          columns={columns}
          storageKey={`evogradient.population.${generation.genIndex}`}
          pageSize={50}
          emptyTitle="no individuals"
          emptyDescription="this generation did not include individual mutation data"
        />
      </PanelCard>
    </div>
  );
}

function PopulationTooltip({ active, payload }: { active?: boolean; payload?: unknown[] }) {
  if (!active || !Array.isArray(payload)) return null;
  const point = (payload[0] as { payload?: PopulationPoint } | undefined)?.payload;
  if (!point) return null;
  return (
    <div className="rounded border border-border bg-bg-2 p-2 text-[11px] shadow-[var(--shadow-popover)]">
      <div className="font-mono text-text">individual {point.individualId}</div>
      <div className="text-muted">lineage {point.lineageId}</div>
      <div className="text-muted">score {formatNumber(point.score)}</div>
      <div className={point.selected ? "text-[--color-ok]" : "text-muted"}>
        {point.selected ? "selected" : "discarded"}
      </div>
      <div className="mt-1 max-w-56 font-mono text-muted">{point.op} {point.path || "root"}</div>
      <div className="max-w-56 truncate text-muted-2">{point.diff}</div>
    </div>
  );
}

function individualRow(
  individual: EvoIndividual,
  activeIndividual: number,
  minScore: number,
  maxScore: number,
): RunRow {
  const active = individual.individualId === activeIndividual;
  return {
    id: `${individual.lineageId}:${individual.individualId}`,
    identity: individual.lineageId,
    state: individual.selected ? "ended" : "queued",
    startedAt: null,
    endedAt: null,
    durationMs: null,
    fields: {
      focus: {
        kind: "pill",
        value: active ? "focus" : individual.selected ? "selected" : "discarded",
        tone: active ? "accent" : individual.selected ? "ok" : "default",
      },
      individual: { kind: "num", value: individual.individualId, format: "int" },
      lineage: { kind: "text", value: individual.lineageId, mono: true },
      parent: { kind: "text", value: individual.parentLineageId ?? "root", mono: true },
      score: { kind: "score", value: individual.score, min: minScore, max: maxScore },
      operator: { kind: "text", value: individual.op, mono: true },
      path: { kind: "text", value: individual.path || "root", mono: true },
      diff: deltaField(individual.parameterDeltas),
    },
  };
}

function generationIndividuals(generation: EvoGeneration | null): EvoIndividual[] {
  if (!generation) return [];
  if (generation.individuals.length > 0) return generation.individuals;
  const survivorSet = new Set(generation.survivorIndices);
  return generation.scores.map((score, individualId) => ({
    individualId,
    lineageId: `legacy-${generation.genIndex}-${individualId}`,
    parentLineageId: null,
    score,
    selected: survivorSet.has(individualId),
    op: "identity",
    path: "",
    improved: false,
    parameterDeltas: [],
  }));
}

function deltaField(deltas: EvoParameterDelta[]): RunFieldValue {
  if (deltas.length === 0) return { kind: "text", value: "no parameter change" };
  const delta = deltas[0];
  if (deltas.length === 1 && delta) {
    return {
      kind: "diff",
      previous: formatValue(delta.before),
      value: formatValue(delta.after),
    };
  }
  return { kind: "text", value: `${deltas.length} parameter changes` };
}

function deltaSummary(deltas: EvoParameterDelta[]): string {
  if (deltas.length === 0) return "no parameter change";
  const delta = deltas[0];
  if (deltas.length === 1 && delta) {
    return `${delta.path}: ${formatValue(delta.before)} -> ${formatValue(delta.after)}`;
  }
  return `${deltas.length} parameter changes`;
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

function parseParamNumber(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function selectIndividualFromPoint(
  point: unknown,
  selectIndividual: (individualId: number) => void,
) {
  const payload = asRecord((point as { payload?: unknown } | null)?.payload) ?? asRecord(point);
  const id = numberValue(payload?.individualId);
  if (id != null) selectIndividual(id);
}
