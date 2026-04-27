import { MarkdownView } from "@/components/ui/markdown";
import type { DebateCritique, DebateProposal, DebateRound } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface RoundCardProps {
  round: DebateRound;
  roundNumber: number;
  expanded?: boolean;
  onToggle?: () => void;
}

export function RoundCard({ round, roundNumber, expanded = false, onToggle }: RoundCardProps) {
  const scores = round.scores;
  const maxScore = scores.length > 0 ? Math.max(...scores) : null;

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-bg-1">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 border-b border-border px-3 py-2 text-left transition-colors hover:bg-bg-2"
        onClick={onToggle}
      >
        <div>
          <div className="text-[12px] font-medium text-text">Round {roundNumber}</div>
          <div className="text-[11px] text-muted">
            {round.proposals.length} proposals · mean score {formatScore(mean(scores))}
          </div>
        </div>
        <span className="text-[11px] text-muted">{expanded ? "collapse" : "expand"}</span>
      </button>

      <div className="grid gap-px bg-border md:grid-cols-3">
        {round.proposals.map((proposal, index) => {
          const critique = findCritique(round.critiques, proposal, index);
          const score = scores[index] ?? critique?.score ?? null;
          const isBest = maxScore != null && score === maxScore;
          return (
            <article key={`${proposal.author || "proposer"}-${index}`} className="bg-bg-1 p-3">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-[12px] font-medium text-text">
                    {proposal.author || `Proposer ${index + 1}`}
                  </div>
                  <div className="text-[11px] text-muted">proposal</div>
                </div>
                {score != null ? (
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 font-mono text-[11px] tabular-nums",
                      isBest
                        ? "bg-[var(--color-ok)]/15 text-[var(--color-ok)]"
                        : "bg-bg-3 text-text",
                    )}
                  >
                    {formatScore(score)}
                  </span>
                ) : null}
              </div>

              <div className={cn(!expanded && "line-clamp-5")}>
                <MarkdownView value={proposal.content || "No proposal text recorded."} />
              </div>

              <div className="mt-3 border-t border-border pt-2">
                <div className="mb-1 text-[11px] font-medium text-muted">
                  Critic score: {formatScore(score)}
                </div>
                <p
                  className={cn(
                    "m-0 whitespace-pre-wrap break-words text-[12px] leading-5 text-text/80",
                    !expanded && "line-clamp-3",
                  )}
                >
                  {critique?.comments || "No critique recorded for this proposal."}
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
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
