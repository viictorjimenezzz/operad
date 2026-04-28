import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { IterationsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";

type IterationEntry = IterationsResponse["iterations"][number];

type Phase = "plan" | "retrieve" | "reason" | "critique" | "reflect";

const PHASES: Phase[] = ["plan", "retrieve", "reason", "critique", "reflect"];

interface PhaseCell {
  phase: Phase;
  score: number | null;
  preview: string;
  full: string;
}

interface AttemptRow {
  attemptIndex: number | null;
  cells: Partial<Record<Phase, PhaseCell>>;
}

export function AutoResearcherAttemptsTab({ dataIterations }: { dataIterations?: unknown }) {
  const parsed = IterationsResponse.safeParse(dataIterations);
  const rows = useMemo(
    () => (parsed.success ? buildAttemptRows(parsed.data.iterations) : []),
    [parsed],
  );
  const [selected, setSelected] = useState<{
    attemptLabel: string;
    cell: PhaseCell;
  } | null>(null);

  if (!parsed.success || rows.length === 0) {
    return (
      <EmptyState
        title="no attempt iterations"
        description="AutoResearcher iteration events have not arrived yet"
      />
    );
  }

  return (
    <>
      <div className="h-full overflow-auto p-4">
        <section className="overflow-x-auto rounded-lg border border-border bg-bg-1">
          <div
            className="grid min-w-[920px] border-b border-border"
            style={{ gridTemplateColumns: "160px repeat(5, minmax(0, 1fr))" }}
          >
            <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
              attempt
            </div>
            {PHASES.map((phase) => (
              <div
                key={phase}
                className="border-l border-border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted"
              >
                {phase}
              </div>
            ))}
          </div>

          {rows.map((row) => {
            const attemptLabel =
              row.attemptIndex == null ? "Attempt unknown" : `Attempt #${row.attemptIndex + 1}`;
            return (
              <div
                key={row.attemptIndex == null ? "unknown" : row.attemptIndex}
                className="grid border-b border-border last:border-b-0"
                style={{ gridTemplateColumns: "160px repeat(5, minmax(0, 1fr))" }}
              >
                <div className="px-3 py-3 text-[12px] font-medium text-text">{attemptLabel}</div>
                {PHASES.map((phase) => {
                  const cell = row.cells[phase];
                  if (!cell) {
                    return (
                      <div key={phase} className="border-l border-border px-3 py-3 text-[11px] text-muted">
                        phase not emitted
                      </div>
                    );
                  }

                  return (
                    <button
                      key={phase}
                      type="button"
                      className={cn(
                        "border-l border-border px-3 py-3 text-left transition-colors hover:bg-bg-2",
                        selected?.cell === cell && "bg-bg-2",
                      )}
                      onClick={() => setSelected({ attemptLabel, cell })}
                      aria-label={`${attemptLabel} ${phase}`}
                    >
                      <div className="mb-1 text-[10px] font-mono text-muted">
                        score {formatScore(cell.score)}
                      </div>
                      <div className="line-clamp-4 text-[11px] leading-5 text-text/90">
                        <MarkdownView value={cell.preview} />
                      </div>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </section>
      </div>

      {selected ? (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/45">
          <button
            type="button"
            aria-label="Close drawer"
            className="h-full flex-1 cursor-default"
            onClick={() => setSelected(null)}
          />
          <aside
            className="h-full w-[min(max(var(--drawer-width),var(--drawer-min)),var(--drawer-max))] border-l border-border bg-bg p-4"
            role="dialog"
            aria-label="Attempt phase output"
          >
            <div className="mb-3 flex items-start justify-between gap-3 border-b border-border pb-3">
              <div>
                <h2 className="m-0 text-[14px] font-semibold text-text">
                  {selected.attemptLabel} · {selected.cell.phase}
                </h2>
                <p className="m-0 mt-1 text-[11px] text-muted">
                  phase score {formatScore(selected.cell.score)}
                </p>
              </div>
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-[11px] text-text hover:bg-bg-2"
                onClick={() => setSelected(null)}
              >
                Close
              </button>
            </div>
            <div className="h-[calc(100%-64px)] overflow-auto pr-1">
              <MarkdownView value={selected.cell.full} />
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

function buildAttemptRows(iterations: IterationEntry[]): AttemptRow[] {
  const byAttempt = new Map<string, { attemptIndex: number | null; entries: IterationEntry[] }>();

  for (const entry of iterations) {
    const attemptIndex =
      typeof entry.metadata.attempt_index === "number" ? entry.metadata.attempt_index : null;
    const key = attemptIndex == null ? "unknown" : String(attemptIndex);
    const bucket = byAttempt.get(key) ?? { attemptIndex, entries: [] };
    bucket.entries.push(entry);
    byAttempt.set(key, bucket);
  }

  return [...byAttempt.values()]
    .map((group) => {
      const cells: Partial<Record<Phase, PhaseCell>> = {};
      for (const phase of PHASES) {
        const phaseEntries = group.entries.filter((entry) => normalizePhase(entry.phase) === phase);
        const picked = phaseEntries.at(-1);
        if (!picked) continue;
        const full = extractPhaseText(picked);
        cells[phase] = {
          phase,
          score: typeof picked.score === "number" ? picked.score : null,
          preview: clampText(full, 280),
          full,
        };
      }
      return { attemptIndex: group.attemptIndex, cells };
    })
    .sort(
      (a, b) =>
        (a.attemptIndex ?? Number.MAX_SAFE_INTEGER) - (b.attemptIndex ?? Number.MAX_SAFE_INTEGER),
    );
}

function normalizePhase(phase: string | null): Phase | null {
  if (phase === "plan" || phase === "retrieve" || phase === "reason" || phase === "critique" || phase === "reflect") {
    return phase;
  }
  return null;
}

function extractPhaseText(entry: IterationEntry): string {
  if (typeof entry.text === "string" && entry.text.length > 0) return entry.text;

  const metadata = entry.metadata as Record<string, unknown>;
  for (const key of [
    "text",
    "output",
    "reasoning",
    "answer",
    "message",
    "critique",
    "reflection",
    "suggested_revision",
  ]) {
    const value = metadata[key];
    if (typeof value === "string" && value.length > 0) return value;
  }

  return "No phase output emitted.";
}

function clampText(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars - 1)}…`;
}

function formatScore(value: number | null): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
