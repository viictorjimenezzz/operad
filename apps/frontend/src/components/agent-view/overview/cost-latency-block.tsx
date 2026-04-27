import { Section, Sparkline, StatTile } from "@/components/ui";
import { RunInvocationsResponse } from "@/lib/types";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/utils";
import { useMemo } from "react";

export interface CostLatencyBlockProps {
  dataInvocations?: unknown;
  invocations?: unknown;
  defaultOpen?: boolean;
}

export function CostLatencyBlock(props: CostLatencyBlockProps) {
  const parsed = RunInvocationsResponse.safeParse(props.dataInvocations ?? props.invocations);
  const rows = parsed.success ? parsed.data.invocations : [];

  const stats = useMemo(() => {
    const latencyValues: number[] = [];
    const tokenValues: number[] = [];
    let totalCost = 0;
    let totalTokens = 0;
    for (const r of rows) {
      if (typeof r.latency_ms === "number") latencyValues.push(r.latency_ms);
      const total = (r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0);
      if (total > 0) tokenValues.push(total);
      totalTokens += total;
      if (typeof r.cost_usd === "number") totalCost += r.cost_usd;
    }
    const avgLatency =
      latencyValues.length > 0
        ? latencyValues.reduce((a, b) => a + b, 0) / latencyValues.length
        : null;
    const p95Latency =
      latencyValues.length >= 2
        ? [...latencyValues].sort((a, b) => a - b)[
            Math.max(0, Math.ceil(latencyValues.length * 0.95) - 1)
          ]
        : null;
    return { latencyValues, tokenValues, totalCost, totalTokens, avgLatency, p95Latency };
  }, [rows]);

  const summary =
    rows.length < 2
      ? "needs 2+ invocations"
      : `${rows.length} invocations · avg ${formatDurationMs(stats.avgLatency)} · ${formatTokens(stats.totalTokens)} tokens`;
  const disabled = rows.length < 2;

  return (
    <Section
      title="Cost & latency"
      summary={summary}
      disabled={disabled}
      defaultOpen={props.defaultOpen ?? false}
    >
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          size="sm"
          label="avg latency"
          value={formatDurationMs(stats.avgLatency)}
          sub={
            stats.latencyValues.length > 1 ? (
              <Sparkline values={stats.latencyValues} width={80} height={18} />
            ) : undefined
          }
        />
        <StatTile size="sm" label="p95 latency" value={formatDurationMs(stats.p95Latency)} />
        <StatTile
          size="sm"
          label="total tokens"
          value={formatTokens(stats.totalTokens)}
          sub={
            stats.tokenValues.length > 1 ? (
              <Sparkline values={stats.tokenValues} width={80} height={18} />
            ) : undefined
          }
        />
        <StatTile size="sm" label="total cost" value={formatCost(stats.totalCost)} />
      </div>
    </Section>
  );
}
