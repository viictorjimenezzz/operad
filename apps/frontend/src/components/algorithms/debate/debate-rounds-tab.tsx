import { RoundCard, buildRoundGridTemplate } from "@/components/algorithms/debate/round-card";
import { DebateConsensusTracker } from "@/components/charts/debate-consensus-tracker";
import { EmptyState } from "@/components/ui/empty-state";
import { hashColor } from "@/lib/hash-color";
import { type DebateRound, DebateRoundsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMemo, useState } from "react";
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
  const [expandedRoundKey, setExpandedRoundKey] = useState<string | null>(null);
  const [activeCell, setActiveCell] = useState<{
    roundKey: string;
    proposalIndex: number;
  } | null>(null);

  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no debate rounds" description="round events have not arrived yet" />;
  }

  const rounds = uniqueRounds(parsed.data);
  if (rounds.length === 0) {
    return <EmptyState title="no debate rounds" description="round events have not arrived yet" />;
  }
  const proposerCount = maxProposalSlots(rounds);
  const gridTemplateColumns = buildRoundGridTemplate(
    proposerCount,
    activeCell?.proposalIndex ?? null,
  );

  return (
    <div className="h-full overflow-auto p-4">
      <table className="w-max min-w-full overflow-hidden rounded-lg border border-border bg-bg-1">
        <thead className="contents">
          <tr
            className="sticky top-0 z-10 grid min-w-max border-b border-border bg-bg-2/95 text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2 backdrop-blur"
            style={{ gridTemplateColumns }}
          >
            <th className="px-3 py-2 text-left font-medium" scope="col">
              Round
            </th>
            {Array.from({ length: proposerCount }, (_, index) => (
              <th
                key={index}
                className="border-l border-border px-3 py-2 text-left font-medium"
                scope="col"
              >
                Proposal {index + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="contents">
          {rounds.map((round, index) => {
            const n = roundNumber(round, index);
            const key = debateRoundKey(round, index);
            const isExpanded = expandedRoundKey === key || activeCell?.roundKey === key;
            return (
              <RoundCard
                key={key}
                round={round}
                roundNumber={n}
                proposerCount={proposerCount}
                gridTemplateColumns={gridTemplateColumns}
                isExpanded={isExpanded}
                activeCellIndex={activeCell?.roundKey === key ? activeCell.proposalIndex : null}
                onToggleRound={() => {
                  setActiveCell(null);
                  setExpandedRoundKey((current) => (current === key ? null : key));
                }}
                onSelectCell={(proposalIndex) => {
                  setExpandedRoundKey(null);
                  setActiveCell((current) =>
                    current?.roundKey === key && current.proposalIndex === proposalIndex
                      ? null
                      : { roundKey: key, proposalIndex },
                  );
                }}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function debateRoundKey(round: DebateRound, index: number): string {
  return round.round_index == null ? `round-pos-${index}` : `round-${round.round_index}`;
}

export function DebateConsensusTab({ data }: { data: unknown }) {
  const parsed = DebateRoundsResponse.safeParse(data);
  const rounds = parsed.success ? uniqueRounds(parsed.data) : [];
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
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto grid max-w-[1320px] gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-4">
          <section className="rounded-lg border border-border bg-bg-1 p-3">
            <div className="mb-2 text-[12px] font-medium text-text">Score evolution</div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData} margin={{ top: 10, right: 24, bottom: 18, left: 0 }}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="round"
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "var(--color-muted)" }}
                  tickFormatter={formatRoundTick}
                />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "var(--color-muted)" }} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-bg-2)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 6,
                    fontSize: 11,
                  }}
                  labelFormatter={(value) => formatRoundTick(Number(value))}
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

          <section className="rounded-lg border border-border bg-bg-1 p-3">
            <div className="mb-2 text-[12px] font-medium text-text">Agreement</div>
            <DebateConsensusTracker data={rounds} height={300} />
          </section>
        </div>

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

function maxProposalSlots(rounds: DebateRound[]): number {
  return Math.max(
    1,
    ...rounds.map((round) =>
      Math.max(round.proposals.length, round.critiques.length, round.scores.length),
    ),
  );
}

function formatRoundTick(value: number): string {
  return Number.isFinite(value) ? `Round ${Math.round(value)}` : "";
}
