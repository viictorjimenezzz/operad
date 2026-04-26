import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import type { RunInvocation } from "@/lib/types";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/utils";
import { useMemo } from "react";

export interface CostLatencySparklinesProps {
  invocations: RunInvocation[];
}

interface SparklineProps {
  label: string;
  values: number[];
  stroke: string;
  formatter: (value: number) => string;
}

export function CostLatencySparklines({ invocations }: CostLatencySparklinesProps) {
  const series = useMemo(
    () => ({
      cost: invocations.map((entry) => entry.cost_usd ?? 0),
      latency: invocations.map((entry) => entry.latency_ms ?? 0),
      tokens: invocations.map(
        (entry) => (entry.prompt_tokens ?? 0) + (entry.completion_tokens ?? 0),
      ),
    }),
    [invocations],
  );

  if (invocations.length < 2) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>cost / latency / tokens</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <EmptyState title="not enough data" description="at least two invocations are required" />
        </CardContent>
      </Card>
    );
  }

  const totalCost = series.cost.reduce((sum, value) => sum + value, 0);
  const avgLatency = series.latency.reduce((sum, value) => sum + value, 0) / series.latency.length;
  const totalTokens = series.tokens.reduce((sum, value) => sum + value, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>cost / latency / tokens</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-3">
          <Sparkline
            label="cost"
            values={series.cost}
            stroke="hsl(145 66% 46%)"
            formatter={(value) => formatCost(value)}
          />
          <Sparkline
            label="latency"
            values={series.latency}
            stroke="hsl(30 88% 53%)"
            formatter={(value) => formatDurationMs(value)}
          />
          <Sparkline
            label="tokens"
            values={series.tokens}
            stroke="hsl(208 83% 55%)"
            formatter={(value) => formatTokens(value)}
          />
        </div>
        <p className="m-0 text-[0.68rem] text-muted">
          total cost: {formatCost(totalCost)} · avg latency: {formatDurationMs(avgLatency)} ·{" "}
          {formatTokens(totalTokens)} tokens
        </p>
      </CardContent>
    </Card>
  );
}

function Sparkline({ label, values, stroke, formatter }: SparklineProps) {
  const points = buildPoints(values, 120, 24);
  return (
    <div className="rounded border border-border bg-bg-2 px-2 py-1.5">
      <div className="mb-1 text-[0.65rem] uppercase tracking-[0.1em] text-muted">{label}</div>
      <svg width="100%" height={24} viewBox="0 0 120 24" className="block">
        <title>{`${label} sparkline`}</title>
        <polyline fill="none" stroke={stroke} strokeWidth={1.8} points={points} />
        {values.map((value, index) => {
          const x = values.length === 1 ? 0 : (index / (values.length - 1)) * 120;
          const y = pointY(value, values, 24);
          return (
            <circle key={`${label}-${index}`} cx={x} cy={y} r={1.6} fill={stroke}>
              <title>{`#${index + 1}: ${formatter(value)}`}</title>
            </circle>
          );
        })}
      </svg>
    </div>
  );
}

function buildPoints(values: number[], width: number, height: number): string {
  if (values.length === 0) return "";
  return values
    .map((value, index) => {
      const x = values.length === 1 ? 0 : (index / (values.length - 1)) * width;
      const y = pointY(value, values, height);
      return `${x},${y}`;
    })
    .join(" ");
}

function pointY(value: number, values: number[], height: number): number {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-9, max - min);
  return height - ((value - min) / span) * height;
}
