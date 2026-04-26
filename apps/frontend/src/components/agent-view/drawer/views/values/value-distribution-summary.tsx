import { ValueDistribution } from "@/components/agent-view/insights/value-distribution";
import { formatNumber } from "@/lib/utils";

interface ValueDistributionSummaryProps {
  label: string;
  values: unknown[];
  side: "in" | "out";
  typeName: string;
}

export function ValueDistributionSummary({
  label,
  values,
  side,
  typeName,
}: ValueDistributionSummaryProps) {
  const unique = new Set(values.map((value) => stringifySafe(value)));
  const counts = new Map<string, number>();
  for (const value of values) {
    const key = stringifySafe(value);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const mostCommon = [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? null;

  return (
    <div className="space-y-2">
      <ValueDistribution label={`${label} (${side})`} values={values} side={side} className="border" />
      <div className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted">
        {formatNumber(values.length)} invocations · {formatNumber(unique.size)} unique · type {typeName}
        {mostCommon ? ` · most common ${truncateLabel(mostCommon[0])}` : ""}
      </div>
    </div>
  );
}

function stringifySafe(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function truncateLabel(value: string, max = 42): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}
