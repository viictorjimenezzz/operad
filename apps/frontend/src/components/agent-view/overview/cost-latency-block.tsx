import { PanelCard, Sparkline, StatTile } from "@/components/ui";
import { hashColor } from "@/lib/hash-color";
import { RunInvocationsResponse } from "@/lib/types";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/utils";
import { useMemo } from "react";

export interface CostLatencyBlockProps {
  dataInvocations?: unknown;
  invocations?: unknown;
  runId?: string;
}

export function CostLatencyBlock(props: CostLatencyBlockProps) {
  const parsed = RunInvocationsResponse.safeParse(props.dataInvocations ?? props.invocations);
  const rows = parsed.success ? parsed.data.invocations : [];

  const stats = useMemo(() => {
    const latencyValues: number[] = [];
    const tokenValues: number[] = [];
    const costValues: number[] = [];
    let totalCost = 0;
    let totalTokens = 0;
    for (const r of rows) {
      if (typeof r.latency_ms === "number") latencyValues.push(r.latency_ms);
      const total = (r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0);
      if (total > 0) tokenValues.push(total);
      totalTokens += total;
      if (typeof r.cost_usd === "number") {
        costValues.push(r.cost_usd);
        totalCost += r.cost_usd;
      }
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
    return {
      latencyValues,
      tokenValues,
      costValues,
      totalCost,
      totalTokens,
      avgLatency,
      p95Latency,
    };
  }, [rows]);

  const hasTokens = stats.totalTokens > 0;
  const hasCost = stats.costValues.length > 0;
  const color = hashColor(props.runId);

  return (
    <PanelCard
      eyebrow="Cost & latency"
      title={
        rows.length === 0
          ? "no invocations yet"
          : `${rows.length} invocations · avg ${formatDurationMs(stats.avgLatency)}`
      }
    >
      {rows.length === 0 ? null : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatTile
            size="sm"
            label="avg latency"
            value={formatDurationMs(stats.avgLatency)}
            sub={
              stats.latencyValues.length > 1 ? (
                <Sparkline values={stats.latencyValues} width={80} height={18} color={color} />
              ) : undefined
            }
          />
          <StatTile
            size="sm"
            label="p95 latency"
            value={rows.length >= 2 ? formatDurationMs(stats.p95Latency) : "needs 2+"}
          />
          <StatTile
            size="sm"
            label="total tokens"
            value={hasTokens ? formatTokens(stats.totalTokens) : "unavailable"}
            sub={
              stats.tokenValues.length > 1 ? (
                <Sparkline values={stats.tokenValues} width={80} height={18} color={color} />
              ) : undefined
            }
          />
          <StatTile
            size="sm"
            label="total cost"
            value={hasCost ? formatCost(stats.totalCost) : "unavailable"}
          />
        </div>
      )}
    </PanelCard>
  );
}
