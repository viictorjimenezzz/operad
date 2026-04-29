import { MarkdownView } from "@/components/ui/markdown";
import type { DebateCritique, DebateProposal, DebateRound } from "@/lib/types";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";
import { useState } from "react";

export interface RoundCardProps {
  round: DebateRound;
  roundNumber: number;
  proposerCount?: number;
  gridTemplateColumns?: string;
}

export function RoundCard({
  round,
  roundNumber,
  proposerCount = round.proposals.length,
  gridTemplateColumns,
}: RoundCardProps) {
  const [reasoningOpen, setReasoningOpen] = useState<Record<number, boolean>>({});
  const scores = round.scores;
  const maxScore = scores.length > 0 ? Math.max(...scores) : null;
  const columnCount = Math.max(
    1,
    proposerCount,
    round.proposals.length,
    round.critiques.length,
    scores.length,
  );
  const template = gridTemplateColumns ?? `112px repeat(${columnCount}, minmax(300px, 360px))`;

  return (
    <div
      role="row"
      className="grid min-w-max border-b border-border last:border-b-0"
      style={{ gridTemplateColumns: template }}
    >
      <div className="flex h-[280px] flex-col justify-between bg-bg-2/50 p-3">
        <div>
          <div className="text-[12px] font-medium text-text">Round {roundNumber}</div>
          <div className="mt-1 text-[11px] text-muted">
            {round.proposals.length} proposals
            <br />
            mean {formatScore(mean(scores))}
          </div>
        </div>
        <div className="font-mono text-[11px] text-muted-2">
          {round.timestamp == null ? "no timestamp" : formatTime(round.timestamp)}
        </div>
      </div>

      {Array.from({ length: columnCount }, (_, index) => {
        const proposal = round.proposals[index] ?? null;
        if (!proposal) {
          return (
            <div
              key={`empty-${index}`}
              role="cell"
              className="flex h-[280px] items-center justify-center border-l border-border bg-bg-1 p-3 text-[12px] text-muted-2"
            >
              No proposal recorded.
            </div>
          );
        }

        const critique = findCritique(round.critiques, proposal, index);
        const score = scores[index] ?? critique?.score ?? null;
        const isBest = maxScore != null && score === maxScore;
        const showReasoning = Boolean(reasoningOpen[index]);
        return (
          <article
            key={`${proposal.author || "proposer"}-${index}`}
            role="cell"
            className="flex h-[280px] min-w-0 flex-col border-l border-border bg-bg-1"
          >
            <div className="flex min-h-12 items-start justify-between gap-2 border-b border-border px-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-[12px] font-medium text-text">
                  {proposal.author || `Proposer ${index + 1}`}
                </div>
                <div className="text-[11px] text-muted">
                  {showReasoning ? "critic reasoning" : "proposal"}
                </div>
              </div>
              {score != null ? (
                <button
                  type="button"
                  className={cn(
                    "inline-flex h-6 min-w-9 items-center justify-center rounded px-1.5 font-mono text-[11px] tabular-nums transition-colors",
                    isBest
                      ? "bg-[var(--color-ok)]/15 text-[var(--color-ok)] hover:bg-[var(--color-ok)]/25"
                      : "bg-bg-3 text-text hover:bg-bg-2",
                  )}
                  aria-label={
                    showReasoning
                      ? `show proposal for ${proposal.author || `Proposer ${index + 1}`}`
                      : `show critic reasoning for ${proposal.author || `Proposer ${index + 1}`}`
                  }
                  onClick={() =>
                    setReasoningOpen((current) => ({
                      ...current,
                      [index]: !current[index],
                    }))
                  }
                >
                  {showReasoning ? <X size={13} /> : formatScore(score)}
                </button>
              ) : null}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
              {showReasoning ? (
                <p className="m-0 whitespace-pre-wrap break-words text-[12px] leading-5 text-text/80">
                  {critique?.comments || "No critique recorded for this proposal."}
                </p>
              ) : (
                <MarkdownView value={proposal.content || "No proposal text recorded."} />
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function findCritique(
  critiques: DebateCritique[],
  proposal: DebateProposal,
  index: number,
): DebateCritique | null {
  if (proposal.author) {
    const match = critiques.find((critique) => critique.target_author === proposal.author);
    if (match) return match;
  }
  return critiques[index] ?? null;
}

function mean(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}

function formatTime(value: number): string {
  return new Date(value * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
