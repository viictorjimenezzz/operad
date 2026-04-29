import {
  buildAutoResearcherAttempts,
  readTerminalScore,
  selectBestAttempt,
} from "@/components/algorithms/auto_researcher/events";
import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { useMemo } from "react";

export function AutoResearcherBestTab({
  dataSummary,
  dataIterations,
  dataEvents,
}: {
  dataSummary?: unknown;
  dataIterations?: unknown;
  dataEvents?: unknown;
}) {
  const terminalScore = readTerminalScore(dataSummary);
  const attempts = useMemo(
    () => buildAutoResearcherAttempts(dataEvents, dataIterations),
    [dataEvents, dataIterations],
  );
  const winner = useMemo(
    () => selectBestAttempt(attempts, terminalScore),
    [attempts, terminalScore],
  );
  const reasoning = winner?.finalReasoning ?? winner?.cells.reason?.text ?? null;
  const answer = winner?.finalAnswer ?? winner?.cells.reason?.text ?? null;
  const confidence = terminalScore ?? winner?.bestScore ?? null;

  return (
    <div className="h-full overflow-auto p-4">
      <section className="rounded-lg border border-border bg-bg-1">
        <header className="border-b border-border px-4 py-3">
          <h2 className="m-0 text-[14px] font-semibold text-text">Best attempt</h2>
          <p className="m-0 mt-1 text-[11px] text-muted">
            {winner
              ? `${winner.attemptIndex == null ? "Attempt unknown" : `Attempt #${winner.attemptIndex + 1}`} selected.`
              : "Winning attempt has not been identified yet."}
          </p>
        </header>
        <div className="grid gap-3 p-4 lg:grid-cols-3">
          <Stat label="confidence" value={formatScore(confidence)} />
          <Stat
            label="attempt"
            value={winner?.attemptIndex == null ? "unknown" : `#${winner.attemptIndex + 1}`}
          />
          <Stat label="terminal score" value={formatScore(terminalScore)} />
        </div>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <article className="rounded-lg border border-border bg-bg-1 p-4">
          <h3 className="m-0 text-[13px] font-semibold text-text">Final reasoning</h3>
          <div className="mt-3">
            {reasoning ? (
              <MarkdownView value={reasoning} />
            ) : (
              <EmptyState
                title="reasoning not emitted"
                description="no reasoning payload was found for the selected attempt"
                className="min-h-40"
              />
            )}
          </div>
        </article>

        <article className="rounded-lg border border-border bg-bg-1 p-4">
          <h3 className="m-0 text-[13px] font-semibold text-text">Final answer</h3>
          <div className="mt-3">
            {answer ? (
              <MarkdownView value={answer} />
            ) : (
              <EmptyState
                title="answer not emitted"
                description="no answer payload was found for the selected attempt"
                className="min-h-40"
              />
            )}
          </div>
        </article>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-bg-2 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.08em] text-muted">{label}</div>
      <div className="mt-1 font-mono text-[12px] text-text">{value}</div>
    </div>
  );
}

function formatScore(value: number | null): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
