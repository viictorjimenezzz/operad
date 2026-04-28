import { ParameterDrawer } from "@/components/agent-view/structure";
import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { RunTable, type RunFieldValue, type RunRow, type RunTableColumn } from "@/components/ui/run-table";
import { IterationsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";

type PhaseKey = "generator" | "reflector" | "refiner";

type PhaseCell = {
  key: PhaseKey;
  label: string;
  text: string;
  score: number | null;
  stopReason: string | null;
  langfuseUrl: string | null;
};

type IterationRow = {
  iterIndex: number;
  generator: PhaseCell;
  reflector: PhaseCell;
  refiner: PhaseCell;
  refineScore: number | null;
  stopReason: string | null;
  langfuseUrl: string | null;
};

type DrawerSelection = {
  iterIndex: number;
  phaseLabel: string;
  score: number | null;
  content: string;
};

const PHASE_LABELS: Record<PhaseKey, string> = {
  generator: "Generator",
  reflector: "Reflector",
  refiner: "Refiner",
};

export function SelfRefineLadderTab({ dataIterations }: { dataIterations?: unknown }) {
  const parsed = IterationsResponse.safeParse(dataIterations);
  const rows = useMemo(
    () => (parsed.success ? buildRows(parsed.data.iterations) : []),
    [parsed.success, parsed.success ? parsed.data.iterations : null],
  );
  const [selected, setSelected] = useState<DrawerSelection | null>(null);

  if (!parsed.success || rows.length === 0) {
    return (
      <EmptyState
        title="no refinement iterations"
        description="iteration events have not arrived yet"
      />
    );
  }

  return (
    <>
      <div className="h-full overflow-auto p-4">
        <div className="min-w-[980px] rounded-lg border border-border bg-bg-1">
          <div className="grid grid-cols-[72px_repeat(3,minmax(0,1fr))_150px] border-b border-border bg-bg-2 px-3 py-2 text-[11px] uppercase tracking-[0.08em] text-muted">
            <span>iter</span>
            <span>Generator</span>
            <span>Reflector</span>
            <span>Refiner</span>
            <span className="text-right">refine_score</span>
          </div>

          <ol className="divide-y divide-border">
            {rows.map((row) => (
              <li
                key={row.iterIndex}
                className="grid grid-cols-[72px_repeat(3,minmax(0,1fr))_150px] items-stretch gap-2 px-3 py-2"
              >
                <div className="flex items-start pt-2 font-mono text-[12px] text-muted">{row.iterIndex}</div>
                {([row.generator, row.reflector, row.refiner] as const).map((cell) => (
                  <button
                    key={`${row.iterIndex}-${cell.key}`}
                    type="button"
                    className={cn(
                      "group rounded-md border bg-bg-1 p-2 text-left transition-colors hover:bg-bg-2",
                      scoreBandClass(cell.score),
                    )}
                    onClick={() =>
                      setSelected({
                        iterIndex: row.iterIndex,
                        phaseLabel: cell.label,
                        score: cell.score,
                        content: cell.text,
                      })
                    }
                  >
                    <div className="mb-1 flex items-center justify-between gap-2 text-[11px]">
                      <span className="font-medium text-text">{cell.label}</span>
                      <span className="font-mono text-muted">{formatScore(cell.score)}</span>
                    </div>
                    <div className="relative text-[12px] leading-5 text-text">
                      <div className="max-h-20 overflow-hidden transition-all group-hover:max-h-64">
                        <MarkdownView value={cell.text} />
                      </div>
                      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-bg-1 to-transparent opacity-100 transition-opacity group-hover:opacity-0" />
                    </div>
                  </button>
                ))}
                <div className="flex items-center justify-end py-1">
                  <ScoreField value={row.refineScore} />
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <ParameterDrawer
        open={selected != null}
        identity={selected ? `selfrefine:${selected.iterIndex}:${selected.phaseLabel}` : "selfrefine"}
        title={selected ? `Iteration ${selected.iterIndex} · ${selected.phaseLabel}` : "phase output"}
        subtitle={selected ? `score ${formatScore(selected.score)}` : undefined}
        onClose={() => setSelected(null)}
      >
        <div className="p-5">
          <MarkdownView value={selected?.content ?? ""} />
        </div>
      </ParameterDrawer>
    </>
  );
}

export function SelfRefineIterationsTab({
  dataIterations,
  runId,
}: {
  dataIterations?: unknown;
  runId?: string;
}) {
  const parsed = IterationsResponse.safeParse(dataIterations);
  const rowsData = useMemo(
    () => (parsed.success ? buildRows(parsed.data.iterations) : []),
    [parsed.success, parsed.success ? parsed.data.iterations : null],
  );

  if (!parsed.success || rowsData.length === 0) {
    return (
      <EmptyState
        title="no refinement iterations"
        description="iteration events have not arrived yet"
      />
    );
  }

  const scoreDomain = scoreRange(rowsData.map((row) => row.refineScore));
  const rows: RunRow[] = rowsData.map((row) => {
    const linkField: RunFieldValue = row.langfuseUrl
      ? { kind: "link", label: "open", to: row.langfuseUrl }
      : { kind: "text", value: "-", mono: true };

    return {
      id: String(row.iterIndex),
      identity: `selfrefine:${row.iterIndex}`,
      state: "ended",
      startedAt: null,
      endedAt: null,
      durationMs: null,
      fields: {
        iter: { kind: "num", value: row.iterIndex, format: "int" },
        refineScore: {
          kind: "score",
          value: row.refineScore,
          min: scoreDomain.min,
          max: scoreDomain.max,
        },
        stopReason: {
          kind: "text",
          value: row.stopReason ?? "max_iter",
          mono: true,
        },
        langfuse: linkField,
      },
    };
  });

  const columns: RunTableColumn[] = [
    { id: "iter", label: "iter", source: "iter", sortable: true, defaultSort: "asc", width: 72 },
    {
      id: "refineScore",
      label: "refine_score",
      source: "refineScore",
      sortable: true,
      width: 180,
    },
    {
      id: "stopReason",
      label: "stop_reason",
      source: "stopReason",
      sortable: true,
      width: "1fr",
    },
    { id: "langfuse", label: "langfuse →", source: "langfuse", width: 92 },
  ];

  return (
    <div className="h-full overflow-auto p-4">
      <RunTable
        rows={rows}
        columns={columns}
        storageKey={runId ? `selfrefine-iterations:${runId}` : "selfrefine-iterations"}
        emptyTitle="no iterations"
        emptyDescription="SelfRefine iterations appear after refinement events"
      />
    </div>
  );
}

function scoreBandClass(score: number | null): string {
  if (score == null) return "border-border";
  if (score >= 0.75) return "border-[--color-ok]";
  if (score >= 0.5) return "border-[--color-warn]";
  return "border-[--color-err]";
}

function formatScore(score: number | null): string {
  return score == null || !Number.isFinite(score) ? "n/a" : score.toFixed(3);
}

function normalizePhase(phase: string | null): PhaseKey | null {
  const key = (phase ?? "").toLowerCase();
  if (key === "generate" || key === "generator") return "generator";
  if (key === "reflect" || key === "reflector") return "reflector";
  if (key === "refine" || key === "refiner") return "refiner";
  return null;
}

function buildRows(entries: IterationsResponse["iterations"]): IterationRow[] {
  const byIteration = new Map<number, IterationsResponse["iterations"]>();
  for (const entry of entries) {
    const bucket = byIteration.get(entry.iter_index) ?? [];
    bucket.push(entry);
    byIteration.set(entry.iter_index, bucket);
  }

  return [...byIteration.entries()]
    .sort(([a], [b]) => a - b)
    .map(([iterIndex, bucket]) => {
      const cells = {
        generator: phaseCell("generator", bucket),
        reflector: phaseCell("reflector", bucket),
        refiner: phaseCell("refiner", bucket),
      };
      return {
        iterIndex,
        generator: cells.generator,
        reflector: cells.reflector,
        refiner: cells.refiner,
        refineScore: cells.refiner.score ?? cells.reflector.score ?? cells.generator.score,
        stopReason:
          cells.refiner.stopReason ?? cells.reflector.stopReason ?? cells.generator.stopReason,
        langfuseUrl:
          cells.refiner.langfuseUrl ?? cells.reflector.langfuseUrl ?? cells.generator.langfuseUrl,
      };
    });
}

function phaseCell(phase: PhaseKey, bucket: IterationsResponse["iterations"]): PhaseCell {
  const matches = bucket.find((entry) => normalizePhase(entry.phase) === phase) ?? null;
  const text = matches?.text?.trim();
  return {
    key: phase,
    label: PHASE_LABELS[phase],
    text: text && text.length > 0 ? text : "No output recorded yet.",
    score: matches?.score ?? null,
    stopReason: metadataString(matches?.metadata, ["stop_reason", "stopReason", "reason"]),
    langfuseUrl: metadataString(matches?.metadata, ["langfuse_url", "langfuseUrl", "url"]),
  };
}

function metadataString(
  metadata: Record<string, unknown> | undefined,
  keys: readonly string[],
): string | null {
  if (!metadata) return null;
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim().length > 0) return value;
  }
  return null;
}

function scoreRange(scores: Array<number | null>): { min: number; max: number } {
  const values = scores.filter((score): score is number => score != null && Number.isFinite(score));
  if (values.length === 0) return { min: 0, max: 1 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) {
    return { min: min - 1, max: max + 1 };
  }
  return { min, max };
}

function ScoreField({ value }: { value: number | null }) {
  const min = 0;
  const max = 1;
  const span = Math.max(max - min, 1e-9);
  const width = value == null ? 0 : Math.max(0, Math.min(1, (value - min) / span)) * 100;
  const tone =
    value == null
      ? "var(--color-muted-2)"
      : value >= 0.75
        ? "var(--color-ok)"
        : value >= 0.5
          ? "var(--color-warn)"
          : "var(--color-err)";

  return (
    <span className="inline-flex w-full min-w-0 items-center gap-2">
      <span className="w-14 flex-shrink-0 text-right font-mono tabular-nums text-[12px] text-text">
        {value == null ? "—" : value.toFixed(3)}
      </span>
      <span className="h-1 w-full rounded-full bg-bg-3">
        <span className="block h-1 rounded-full" style={{ width: `${width}%`, background: tone }} />
      </span>
    </span>
  );
}
