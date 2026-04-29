import { EmptyState } from "@/components/ui/empty-state";
import { type DebateRound, DebateRoundsResponse } from "@/lib/types";
import { useState } from "react";

export function DebateTranscript({ data }: { data: unknown }) {
  const parsed = DebateRoundsResponse.safeParse(data);
  const [expandedRound, setExpandedRound] = useState<number | null>(null);

  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no transcript yet" description="round events haven't arrived yet" />;
  }

  const rounds = uniqueRounds(parsed.data);
  const firstRound = rounds[0];
  if (!firstRound) {
    return <EmptyState title="no transcript yet" description="round events haven't arrived yet" />;
  }
  const activeRound = expandedRound ?? roundNumber(firstRound, 0);

  return (
    <ol className="flex flex-col gap-3 text-xs">
      {rounds.map((round, roundIdx) => {
        const idx = roundNumber(round, roundIdx);
        const scores = round.scores;
        const maxScore = scores.length > 0 ? Math.max(...scores) : 0;
        const winnerIdx = scores.indexOf(maxScore);
        const winner =
          round.proposals[winnerIdx]?.author ||
          (winnerIdx >= 0 ? `Proposer ${winnerIdx + 1}` : null);

        const mean = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
        const variance =
          scores.length > 1 ? scores.reduce((a, s) => a + (s - mean) ** 2, 0) / scores.length : 0;
        const agreement = Math.max(0, Math.min(1, 1 - Math.sqrt(variance) / 0.5));

        const isExpanded = activeRound === idx;

        return (
          <li key={idx} className="rounded-md border border-border bg-bg-2">
            <button
              type="button"
              className="flex w-full items-center justify-between p-3 text-left"
              onClick={() => setExpandedRound(isExpanded ? -1 : idx)}
            >
              <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">
                Round {idx}
              </span>
              <div className="flex items-center gap-3">
                {winner && (
                  <span className="rounded-full bg-ok/20 px-2 py-0.5 text-[0.65rem] font-medium text-ok">
                    winner: {winner}
                  </span>
                )}
                <span className="font-mono text-muted">
                  agreement {(agreement * 100).toFixed(0)}%
                </span>
                <span className="text-muted">{isExpanded ? "▲" : "▼"}</span>
              </div>
            </button>

            {isExpanded && (
              <div className="flex flex-col gap-2 border-t border-border px-3 pb-3 pt-2">
                {round.proposals.map((proposal, pIdx) => {
                  const score = scores[pIdx] ?? null;
                  const critique =
                    round.critiques.find((c) => c.target_author === proposal.author) ??
                    round.critiques[pIdx] ??
                    null;
                  const isWinner = pIdx === winnerIdx && maxScore > 0;

                  return (
                    <div
                      key={pIdx}
                      className={`rounded border p-2 ${
                        isWinner ? "border-ok/40 bg-ok/5" : "border-border bg-bg-3"
                      }`}
                    >
                      <div className="mb-1 flex items-center justify-between">
                        <span className="font-mono font-medium text-text">
                          {proposal.author || `Proposer ${pIdx + 1}`}
                        </span>
                        {score !== null && (
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-bg-1">
                              <div
                                className="h-full rounded-full transition-all"
                                style={{
                                  width: `${Math.min(100, score * 100)}%`,
                                  background: isWinner ? "var(--color-ok)" : "var(--color-accent)",
                                }}
                              />
                            </div>
                            <span className="w-10 text-right font-mono tabular-nums text-text">
                              {score.toFixed(2)}
                            </span>
                          </div>
                        )}
                      </div>

                      <p className="whitespace-pre-wrap text-text/80 leading-relaxed">
                        {proposal.content || <span className="text-muted italic">no content</span>}
                      </p>

                      {critique && (
                        <details className="mt-2">
                          <summary className="cursor-pointer text-muted hover:text-text">
                            critic feedback
                          </summary>
                          <p className="mt-1 whitespace-pre-wrap text-text/70 leading-relaxed">
                            {critique.comments}
                          </p>
                        </details>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function roundNumber(round: DebateRound, index: number): number {
  return (round.round_index ?? index) + 1;
}

function uniqueRounds(rounds: DebateRound[]): DebateRound[] {
  const seen = new Set<number>();
  const unique: DebateRound[] = [];
  for (const round of rounds) {
    if (round.round_index != null) {
      if (seen.has(round.round_index)) continue;
      seen.add(round.round_index);
    }
    unique.push(round);
  }
  return unique.sort((a, b) => {
    if (a.round_index == null && b.round_index == null) return 0;
    if (a.round_index == null) return 1;
    if (b.round_index == null) return -1;
    return a.round_index - b.round_index;
  });
}
