import { RoundCard } from "@/components/algorithms/debate/round-card";
import { DebateConsensusTracker } from "@/components/charts/debate-consensus-tracker";
import { EmptyState } from "@/components/ui/empty-state";
import { useUrlState } from "@/hooks/use-url-state";
import { hashColor } from "@/lib/hash-color";
import { type DebateRound, DebateRoundsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function DebateRoundsTab({ data }: { data: unknown }) {
  const parsed = DebateRoundsResponse.safeParse(data);
  const [roundParam, setRoundParam] = useUrlState("round");
  const pinnedRound = parsePositiveInt(roundParam);
  const [expandedRound, setExpandedRound] = useState<number | null>(pinnedRound);

  useEffect(() => {
    if (pinnedRound != null) setExpandedRound(pinnedRound);
  }, [pinnedRound]);

  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no debate rounds" description="round events have not arrived yet" />;
  }

  const rounds = parsed.data;
  const firstRound = rounds[0];
  if (!firstRound) {
    return <EmptyState title="no debate rounds" description="round events have not arrived yet" />;
  }
  const activeRound = expandedRound ?? roundNumber(firstRound, 0);

  return (
    <div className="flex h-full flex-col overflow-auto p-4">
      <div className="sticky top-0 z-10 -mx-4 -mt-4 mb-4 border-b border-border bg-bg/95 px-4 py-3 backdrop-blur">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div className="text-[12px] font-medium text-text">Pinned round</div>
          <div className="font-mono text-[11px] text-muted">?round={activeRound}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {rounds.map((round, index) => {
            const n = roundNumber(round, index);
            return (
              <button
                key={n}
                type="button"
                className={cn(
                  "rounded border px-2 py-1 text-[11px] transition-colors",
                  n === activeRound
                    ? "border-accent bg-accent/10 text-text"
                    : "border-border bg-bg-1 text-muted hover:border-border-strong hover:text-text",
                )}
                aria-pressed={n === activeRound}
                onClick={() => {
                  setExpandedRound(n);
                  setRoundParam(String(n));
                }}
              >
                Round {n}
              </button>
            );
          })}
        </div>
      </div>

      <ol className="flex flex-col gap-3">
        {rounds.map((round, index) => {
          const n = roundNumber(round, index);
          return (
            <li key={n}>
              <RoundCard
                round={round}
                roundNumber={n}
                expanded={n === activeRound}
                onToggle={() => {
                  const next = n === activeRound ? null : n;
                  setExpandedRound(next);
                  setRoundParam(next == null ? null : String(next));
                }}
              />
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function DebateConsensusTab({ data }: { data: unknown }) {
  const parsed = DebateRoundsResponse.safeParse(data);
  const rounds = parsed.success ? parsed.data : [];
  const maxProposers = Math.max(0, ...rounds.map((round) => round.scores.length));
  const chartData = useMemo(() => buildScoreRows(rounds, maxProposers), [rounds, maxProposers]);
  const finalRound = rounds[rounds.length - 1];
  const finalScores = finalRound?.scores ?? [];
  const finalBestIndex =
    finalScores.length > 0 ? finalScores.indexOf(Math.max(...finalScores)) : -1;

  if (rounds.length === 0) {
    return <EmptyState title="no consensus data" description="round scores have not arrived yet" />;
  }

  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="rounded-lg border border-border bg-bg-1 p-3">
        <div className="mb-2 text-[12px] font-medium text-text">Score evolution</div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 10, right: 24, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
            <XAxis dataKey="round" tick={{ fontSize: 11, fill: "var(--color-muted)" }} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "var(--color-muted)" }} />
            <Tooltip
              contentStyle={{
                background: "var(--color-bg-2)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                fontSize: 11,
              }}
            />
            <Line
              type="monotone"
              dataKey="mean"
              name="mean"
              stroke="var(--color-accent)"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "var(--color-accent)" }}
              connectNulls
            />
            {Array.from({ length: maxProposers }, (_, index) => (
              <Line
                key={index}
                type="monotone"
                dataKey={`p${index}`}
                name={`proposer ${index + 1}`}
                stroke={hashColor(`debate-proposer-${index}`)}
                strokeWidth={index === finalBestIndex ? 2.5 : 1.5}
                dot={{ r: index === finalBestIndex ? 4 : 2 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </section>

      <div className="flex flex-col gap-4">
        <section className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2 text-[12px] font-medium text-text">Agreement</div>
          <DebateConsensusTracker data={rounds} height={180} />
        </section>
        <section className="rounded-lg border border-border bg-bg-1 p-3">
          <div className="mb-2 text-[12px] font-medium text-text">Final proposer ranking</div>
          <div className="flex flex-col gap-2">
            {finalScores.map((score, index) => {
              const proposal = finalRound?.proposals[index];
              return (
                <div
                  key={index}
                  className={cn(
                    "rounded border p-2",
                    index === finalBestIndex
                      ? "border-[var(--color-ok)] bg-[var(--color-ok)]/5"
                      : "border-border bg-bg-2",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[12px] font-medium text-text">
                      {proposal?.author || `Proposer ${index + 1}`}
                    </span>
                    <span className="font-mono text-[11px] tabular-nums text-text">
                      {score.toFixed(2)}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-3 text-[11px] leading-5 text-muted">
                    {proposal?.content || "No final-round proposal text recorded."}
                  </p>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

function roundNumber(round: DebateRound, index: number): number {
  return (round.round_index ?? index) + 1;
}

function parsePositiveInt(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function buildScoreRows(
  rounds: DebateRound[],
  maxProposers: number,
): Array<Record<string, number | null>> {
  return rounds.map((round, index) => {
    const row: Record<string, number | null> = {
      round: roundNumber(round, index),
      mean: mean(round.scores),
    };
    for (let i = 0; i < maxProposers; i++) {
      row[`p${i}`] = round.scores[i] ?? null;
    }
    return row;
  });
}

function mean(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}
