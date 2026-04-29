import { EmptyState } from "@/components/ui/empty-state";
import { type DebateRound, DebateRoundsResponse } from "@/lib/types";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function _agreement(scores: number[]): number {
  if (scores.length < 2) return 1;
  const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
  const variance = scores.reduce((a, s) => a + (s - mean) ** 2, 0) / scores.length;
  return Math.max(0, Math.min(1, 1 - Math.sqrt(variance) / 0.5));
}

export function DebateConsensusTracker({
  data,
  height = 220,
}: {
  data: unknown;
  height?: number;
}) {
  const parsed = DebateRoundsResponse.safeParse(data);
  const rounds = parsed.success ? uniqueRounds(parsed.data) : [];

  if (rounds.length < 2) {
    return (
      <EmptyState
        title="not enough rounds"
        description="consensus tracker needs at least 2 completed rounds"
      />
    );
  }

  const chartData = rounds.map((round, i) => ({
    round: roundNumber(round, i),
    agreement: Number.parseFloat(_agreement(round.scores).toFixed(3)),
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
        <XAxis
          dataKey="round"
          allowDecimals={false}
          tick={{ fontSize: 10, fill: "var(--color-muted)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={formatRoundTick}
          label={{
            value: "round",
            position: "insideBottomRight",
            offset: -4,
            fontSize: 10,
            fill: "var(--color-muted)",
          }}
        />
        <YAxis
          domain={[0, 1]}
          tick={{ fontSize: 10, fill: "var(--color-muted)" }}
          tickLine={false}
          axisLine={false}
          width={32}
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            fontSize: 11,
          }}
          formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "agreement"]}
          labelFormatter={(l) => formatRoundTick(Number(l))}
        />
        <Line
          type="monotone"
          dataKey="agreement"
          stroke="var(--color-accent)"
          strokeWidth={2}
          dot={{ r: 3, fill: "var(--color-accent)", strokeWidth: 0 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
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

export function formatRoundTick(value: number): string {
  return Number.isFinite(value) ? `Round ${Math.round(value)}` : "";
}
