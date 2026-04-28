import {
  AUTO_RESEARCHER_PHASES,
  type AutoResearcherAttempt,
  type AutoResearcherPhaseCell,
  buildAutoResearcherAttempts,
} from "@/components/algorithms/auto_researcher/events";
import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";

export function AutoResearcherAttemptsTab({
  dataIterations,
  dataEvents,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
}) {
  const rows = useMemo(
    () => buildAutoResearcherAttempts(dataEvents, dataIterations),
    [dataEvents, dataIterations],
  );
  const [selected, setSelected] = useState<{
    attemptLabel: string;
    cell: AutoResearcherPhaseCell;
  } | null>(null);

  if (rows.length === 0) {
    return (
      <EmptyState
        title="no attempt iterations"
        description="AutoResearcher events have not arrived yet"
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
            {AUTO_RESEARCHER_PHASES.map((phase) => (
              <div
                key={phase}
                className="border-l border-border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted"
              >
                {phase}
              </div>
            ))}
          </div>

          {rows.map((row) => {
            const attemptLabel = attemptName(row);
            return (
              <div
                key={row.attemptIndex == null ? "unknown" : row.attemptIndex}
                className="grid border-b border-border last:border-b-0"
                style={{ gridTemplateColumns: "160px repeat(5, minmax(0, 1fr))" }}
              >
                <div className="px-3 py-3 text-[12px] font-medium text-text">{attemptLabel}</div>
                {AUTO_RESEARCHER_PHASES.map((phase) => {
                  const cell = row.cells[phase];
                  if (!cell) {
                    return (
                      <div
                        key={phase}
                        className="border-l border-border px-3 py-3 text-[11px] text-muted"
                      >
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
                        <MarkdownView value={clampText(cell.text, 280)} />
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
          <dialog
            open
            className="static m-0 h-full max-h-none w-[min(max(var(--drawer-width),var(--drawer-min)),var(--drawer-max))] max-w-none border-0 border-l border-border bg-bg p-4 text-text"
            aria-label="Attempt phase output"
          >
            <div className="mb-3 flex items-start justify-between gap-3 border-b border-border pb-3">
              <div>
                <h2 className="m-0 text-[14px] font-semibold text-text">
                  {selected.attemptLabel} - {selected.cell.phase}
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
              <MarkdownView value={selected.cell.text} />
            </div>
          </dialog>
        </div>
      ) : null}
    </>
  );
}

function attemptName(attempt: AutoResearcherAttempt): string {
  return attempt.attemptIndex == null ? "Attempt unknown" : `Attempt #${attempt.attemptIndex + 1}`;
}

function clampText(value: string, maxChars: number): string {
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars - 1)}...`;
}

function formatScore(value: number | null): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
