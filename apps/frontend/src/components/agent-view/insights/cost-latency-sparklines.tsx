import type { AgentInvocation } from "@/lib/types";
import { formatDurationMs, formatTokens } from "@/lib/utils";

interface CostLatencySparklinesProps {
  invocations: AgentInvocation[];
}

function points(values: number[], w = 120, h = 24): string {
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${x},${y}`;
    })
    .join(" ");
}

function Spark({ label, values, stroke }: { label: string; values: number[]; stroke: string }) {
  if (values.length < 2) {
    return (
      <div className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted">
        {label}: not enough data
      </div>
    );
  }
  return (
    <div className="rounded border border-border bg-bg-2 px-2 py-1">
      <div className="text-[11px] text-muted">{label}</div>
      <svg
        width="120"
        height="24"
        viewBox="0 0 120 24"
        role="img"
        aria-label={`${label} sparkline`}
      >
        <polyline fill="none" stroke={stroke} strokeWidth="1.5" points={points(values)} />
      </svg>
    </div>
  );
}

export function CostLatencySparklines({ invocations }: CostLatencySparklinesProps) {
  const latency = invocations.map((v) => v.latency_ms ?? 0);
  const tokens = invocations.map((v) => (v.prompt_tokens ?? 0) + (v.completion_tokens ?? 0));
  const cost = invocations.map(
    (v) => ((v.prompt_tokens ?? 0) + (v.completion_tokens ?? 0)) / 1_000_000,
  );

  const totalTokens = tokens.reduce((a, b) => a + b, 0);
  const avgLatency = latency.length ? latency.reduce((a, b) => a + b, 0) / latency.length : 0;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Spark label="cost" values={cost} stroke="var(--color-ok)" />
        <Spark label="latency" values={latency} stroke="var(--color-warn)" />
        <Spark label="tokens" values={tokens} stroke="var(--color-accent)" />
      </div>
      <div className="text-[11px] text-muted">
        total tokens: {formatTokens(totalTokens)} · avg latency: {formatDurationMs(avgLatency)}
      </div>
    </div>
  );
}
