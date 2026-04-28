import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { IterationsResponse } from "@/lib/types";
import { useMemo } from "react";

type IterationEntry = IterationsResponse["iterations"][number];

interface BestAttempt {
  attemptIndex: number | null;
  score: number | null;
}

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
  const iterations = readIterations(dataIterations);
  const events = parseEvents(dataEvents);

  const winner = useMemo(
    () => selectBestAttempt(iterations, terminalScore),
    [iterations, terminalScore],
  );

  const winnerEvents = useMemo(
    () => filterAttemptEvents(events, winner?.attemptIndex ?? null),
    [events, winner?.attemptIndex],
  );

  const reasoning = latestField(
    winnerEvents,
    ["reasoning", "analysis", "rationale", "text", "output"],
    ["reason"],
  );
  const answer = latestField(
    winnerEvents,
    ["answer", "final_answer", "response", "text", "output"],
    ["reflect", "reason"],
  );
  const confidence = terminalScore ?? winner?.score ?? null;

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

function readIterations(data: unknown): IterationEntry[] {
  const parsed = IterationsResponse.safeParse(data);
  return parsed.success ? parsed.data.iterations : [];
}

function readTerminalScore(summary: unknown): number | null {
  if (!summary || typeof summary !== "object") return null;
  const value = (summary as Record<string, unknown>).algorithm_terminal_score;
  return typeof value === "number" ? value : null;
}

function parseEvents(data: unknown): unknown[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).events)) {
    return (data as Record<string, unknown>).events as unknown[];
  }
  return [];
}

function selectBestAttempt(iterations: IterationEntry[], terminalScore: number | null): BestAttempt | null {
  const scoresByAttempt = new Map<number | null, number>();

  for (const entry of iterations) {
    if (typeof entry.score !== "number") continue;
    const attemptIndex =
      typeof entry.metadata.attempt_index === "number" ? entry.metadata.attempt_index : null;
    const current = scoresByAttempt.get(attemptIndex);
    if (current == null || entry.score > current) scoresByAttempt.set(attemptIndex, entry.score);
  }

  const attempts = [...scoresByAttempt.entries()].map(([attemptIndex, score]) => ({
    attemptIndex,
    score,
  }));
  if (attempts.length === 0) return null;

  if (terminalScore != null) {
    return [...attempts].sort((a, b) => {
      const aDelta = Math.abs((a.score ?? 0) - terminalScore);
      const bDelta = Math.abs((b.score ?? 0) - terminalScore);
      if (aDelta !== bDelta) return aDelta - bDelta;
      return (b.score ?? -Infinity) - (a.score ?? -Infinity);
    })[0] ?? null;
  }

  return [...attempts].sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity))[0] ?? null;
}

function filterAttemptEvents(events: unknown[], attemptIndex: number | null): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = [];
  for (const event of events) {
    if (!event || typeof event !== "object") continue;
    const record = event as Record<string, unknown>;
    if (record.type !== "algo_event") continue;
    const payload =
      record.payload && typeof record.payload === "object"
        ? (record.payload as Record<string, unknown>)
        : null;
    if (!payload) continue;

    const eventAttempt =
      typeof payload.attempt_index === "number" ? payload.attempt_index : null;
    if (eventAttempt === attemptIndex) out.push(payload);
  }
  return out;
}

function latestField(
  payloads: Array<Record<string, unknown>>,
  keys: string[],
  preferredPhases: string[],
): string | null {
  const prioritized = [...payloads].sort((a, b) => {
    const phaseA = typeof a.phase === "string" ? a.phase : "";
    const phaseB = typeof b.phase === "string" ? b.phase : "";
    const rankA = phaseRank(phaseA, preferredPhases);
    const rankB = phaseRank(phaseB, preferredPhases);
    return rankA - rankB;
  });

  for (let i = prioritized.length - 1; i >= 0; i -= 1) {
    const payload = prioritized[i];
    if (!payload) continue;
    for (const key of keys) {
      const value = payload[key];
      if (typeof value === "string" && value.length > 0) return value;
    }
  }

  return null;
}

function phaseRank(phase: string, preferredPhases: string[]): number {
  const idx = preferredPhases.indexOf(phase);
  return idx === -1 ? preferredPhases.length + 1 : idx;
}

function formatScore(value: number | null): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
