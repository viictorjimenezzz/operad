import { EmptyState, Pill } from "@/components/ui";
import { useAgentGroup, useAgentGroupMetrics } from "@/hooks/use-runs";
import { AgentGroupMetricsResponse, RunSummary } from "@/lib/types";
import { cn, formatCost, formatDurationMs, formatNumber, formatTokens } from "@/lib/utils";

export interface MetricsValueTableProps {
  dataSummary?: unknown;
  sourceSummary?: unknown;
  sourceGroupMetrics?: unknown;
  runId?: string | undefined;
  hashContent?: string | undefined;
}

type MetricRow = {
  key: string;
  label: string;
  value: number | null;
  format: "ms" | "tokens" | "cost" | "score" | "number";
};

export function MetricsValueTable(props: MetricsValueTableProps) {
  const summary = RunSummary.safeParse(props.dataSummary ?? props.sourceSummary);
  const run = summary.success ? summary.data : null;
  const hash = props.hashContent ?? run?.hash_content ?? null;
  const group = useAgentGroup(hash);
  const metrics = useAgentGroupMetrics(hash);
  const sourceMetrics = AgentGroupMetricsResponse.safeParse(props.sourceGroupMetrics);
  const groupMetrics = sourceMetrics.success ? sourceMetrics.data : metrics.data;

  if (!run) {
    return (
      <EmptyState
        title="metrics unavailable"
        description="the run summary has not loaded enough data for this table"
      />
    );
  }

  const rows = metricRows(run);
  const groupSize = group.data?.runs.length ?? 0;
  const showDelta =
    groupSize >= 2 || Object.values(groupMetrics?.metrics ?? {}).some((m) => m.series.length >= 2);

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-bg-1">
      <div
        className={cn(
          "grid min-h-8 items-center gap-3 border-b border-border bg-bg-2 px-3 text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2",
          showDelta ? "grid-cols-[minmax(0,1fr)_120px_160px]" : "grid-cols-[minmax(0,1fr)_120px]",
        )}
      >
        <span>Metric</span>
        <span className="text-right">Value</span>
        {showDelta ? <span className="text-right">Delta vs group p50</span> : null}
      </div>
      {rows.map((row) => {
        const p50 = medianFor(row.key, groupMetrics, group.data?.runs ?? []);
        const delta = p50 != null && row.value != null ? deltaPercent(row.value, p50) : null;
        return (
          <div
            key={row.key}
            className={cn(
              "grid min-h-9 items-center gap-3 border-b border-border px-3 text-[12px] last:border-b-0",
              showDelta
                ? "grid-cols-[minmax(0,1fr)_120px_160px]"
                : "grid-cols-[minmax(0,1fr)_120px]",
            )}
          >
            <span className="min-w-0 truncate font-medium text-text">{row.label}</span>
            <span className="text-right font-mono tabular-nums text-text">
              {formatMetric(row.value, row.format)}
            </span>
            {showDelta ? (
              <span className="text-right">
                {delta == null || p50 == null ? (
                  <span className="text-muted-2">-</span>
                ) : (
                  <Pill tone={deltaTone(row.key, delta)} size="sm">
                    {formatDelta(delta)} (p50 {formatMetric(p50, row.format)})
                  </Pill>
                )}
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function metricRows(run: RunSummary): MetricRow[] {
  const rows: MetricRow[] = [
    { key: "latency_ms", label: "latency_ms", value: run.duration_ms, format: "ms" },
    { key: "prompt_tokens", label: "prompt_tokens", value: run.prompt_tokens, format: "tokens" },
    {
      key: "completion_tokens",
      label: "completion_tokens",
      value: run.completion_tokens,
      format: "tokens",
    },
    { key: "cost_usd", label: "cost_usd", value: run.cost?.cost_usd ?? null, format: "cost" },
  ];
  for (const [key, value] of Object.entries(run.metrics ?? {})) {
    if (rows.some((row) => row.key === key)) continue;
    rows.push({ key, label: key, value, format: metricFormat(key) });
  }
  return rows;
}

function medianFor(
  key: string,
  metrics: AgentGroupMetricsResponse | undefined,
  runs: RunSummary[],
): number | null {
  const endpointValues = metrics?.metrics[key]?.series
    .map((point) => point.value)
    .filter((value): value is number => value != null && Number.isFinite(value));
  if (endpointValues && endpointValues.length > 0) return median(endpointValues);
  const values = runs
    .map((run) => runMetric(run, key))
    .filter((value): value is number => value != null && Number.isFinite(value));
  return values.length > 0 ? median(values) : null;
}

function runMetric(run: RunSummary, key: string): number | null {
  switch (key) {
    case "latency_ms":
      return run.duration_ms;
    case "prompt_tokens":
      return run.prompt_tokens;
    case "completion_tokens":
      return run.completion_tokens;
    case "cost_usd":
      return run.cost?.cost_usd ?? null;
    default:
      return run.metrics?.[key] ?? null;
  }
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[mid] ?? 0;
  return ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
}

function deltaPercent(value: number, p50: number): number {
  if (p50 === 0) return value === 0 ? 0 : 1;
  return (value - p50) / Math.abs(p50);
}

function deltaTone(key: string, delta: number): "ok" | "warn" | "error" | "default" {
  if (Math.abs(delta) < 0.05) return "default";
  const lowerIsBetter =
    key.includes("latency") ||
    key.includes("tokens") ||
    key.includes("cost") ||
    key.includes("error");
  const better = lowerIsBetter ? delta < 0 : delta > 0;
  if (better) return "ok";
  return Math.abs(delta) > 0.25 ? "error" : "warn";
}

function formatDelta(delta: number): string {
  const pct = Math.round(delta * 100);
  return `${pct >= 0 ? "+" : ""}${pct}%`;
}

function metricFormat(key: string): MetricRow["format"] {
  if (key.includes("latency") || key.endsWith("_ms")) return "ms";
  if (key.includes("token")) return "tokens";
  if (key.includes("cost") || key.includes("usd")) return "cost";
  if (key.includes("score") || key.includes("match") || key.includes("rate")) return "score";
  return "number";
}

function formatMetric(value: number | null, format: MetricRow["format"]): string {
  if (value == null || !Number.isFinite(value)) return "-";
  switch (format) {
    case "ms":
      return formatDurationMs(value);
    case "tokens":
      return formatTokens(value);
    case "cost":
      return formatCost(value);
    case "score":
      return value.toFixed(3);
    default:
      return formatNumber(value);
  }
}
