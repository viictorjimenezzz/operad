import {
  Eyebrow,
  MetricSeriesChart,
  MultiSeriesChart,
  PanelCard,
  PanelGrid,
  PanelSection,
} from "@/components/ui";
import { useAgentGroup, useAgentGroupMetrics } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { formatCost, formatDurationMs, formatNumber, formatTokens } from "@/lib/utils";
import { useParams } from "react-router-dom";

type MetricDef = {
  key: string;
  label: string;
  format: "ms" | "tokens" | "cost" | "score" | "number";
  source: string;
};

const BUILT_INS: MetricDef[] = [
  { key: "latency_ms", label: "Latency", format: "ms", source: "built-in" },
  { key: "prompt_tokens", label: "Prompt tokens", format: "tokens", source: "built-in" },
  { key: "completion_tokens", label: "Completion tokens", format: "tokens", source: "built-in" },
  { key: "cost_usd", label: "Cost", format: "cost", source: "built-in" },
  { key: "error_rate", label: "Error rate", format: "score", source: "built-in" },
  {
    key: "schema_validation_rate",
    label: "Output schema validation",
    format: "score",
    source: "built-in",
  },
];

export function AgentGroupMetricsTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const endpoint = useAgentGroupMetrics(hashContent);

  if (!hashContent || !group.data) return null;
  const runs = [...group.data.runs].sort((a, b) => a.started_at - b.started_at);
  const N = runs.length;
  const agentPath = runs.at(-1)?.root_agent_path ?? null;
  const metricDefs = allMetricDefs(
    runs,
    endpoint.data?.metrics ? Object.keys(endpoint.data.metrics) : [],
    agentPath,
  );

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-4">
        {N >= 2 ? (
          <PanelSection label="Cost vs latency">
            <PanelGrid cols={2}>
              <PanelCard title="Cost vs latency" eyebrow="USD vs ms" bodyMinHeight={260}>
                <MultiSeriesChart
                  series={[{ id: hashContent, points: scatterPoints(runs, "cost_usd") }]}
                  height={240}
                  formatX={(n) => formatDurationMs(n)}
                  formatY={(n) => formatCost(n)}
                  xLabel="latency"
                  yLabel="cost"
                />
              </PanelCard>
              <PanelCard title="Tokens vs latency" eyebrow="tokens vs ms" bodyMinHeight={260}>
                <MultiSeriesChart
                  series={[{ id: hashContent, points: scatterPoints(runs, "tokens") }]}
                  height={240}
                  formatX={(n) => formatDurationMs(n)}
                  formatY={(n) => formatTokens(n)}
                  xLabel="latency"
                  yLabel="tokens"
                />
              </PanelCard>
            </PanelGrid>
          </PanelSection>
        ) : null}
        <PanelSection label="Metrics" count={metricDefs.length}>
          {N === 1 ? (
            <MetricTable runs={runs} metricDefs={metricDefs} endpoint={endpoint.data} />
          ) : N <= 4 ? (
            <MiniBars runs={runs} metricDefs={metricDefs} endpoint={endpoint.data} />
          ) : (
            <SeriesCharts
              runs={runs}
              metricDefs={metricDefs}
              endpoint={endpoint.data}
              hashContent={hashContent}
            />
          )}
        </PanelSection>
      </div>
    </div>
  );
}

function MetricTable({
  runs,
  metricDefs,
  endpoint,
}: {
  runs: RunSummary[];
  metricDefs: MetricDef[];
  endpoint: { metrics: Record<string, { series: Array<{ run_id: string; started_at: number; value: number | null }> }> } | undefined;
}) {
  const run = runs[0];
  if (!run) return null;
  return (
    <div className="divide-y divide-border">
      {metricDefs.map((metric) => {
        const points = seriesPoints(runs, metric.key, endpoint?.metrics[metric.key]?.series);
        const value = points[0]?.y ?? null;
        return (
          <div key={metric.key} className="grid grid-cols-[1fr_auto_80px] items-center gap-4 py-2 px-1">
            <div className="min-w-0">
              <Eyebrow>{metric.source}</Eyebrow>
              <span className="text-[13px] text-text">{metric.label}</span>
            </div>
            <span className="text-[13px] text-muted">
              {value != null ? formatMetric(value, metric.format) : "—"}
            </span>
            <span className="text-[11px] text-muted-2 text-right">{metric.format}</span>
          </div>
        );
      })}
    </div>
  );
}

function MiniBars({
  runs,
  metricDefs,
  endpoint,
}: {
  runs: RunSummary[];
  metricDefs: MetricDef[];
  endpoint: { metrics: Record<string, { series: Array<{ run_id: string; started_at: number; value: number | null }> }> } | undefined;
}) {
  return (
    <div className="space-y-4">
      {metricDefs.map((metric) => {
        const points = seriesPoints(runs, metric.key, endpoint?.metrics[metric.key]?.series);
        const values = points.map((p) => p.y).filter((v): v is number => v != null);
        const max = values.length > 0 ? Math.max(...values) : 1;
        return (
          <div key={metric.key} className="space-y-1">
            <Eyebrow>{metric.source}</Eyebrow>
            <div className="text-[12px] font-medium text-text">{metric.label}</div>
            <div className="flex items-end gap-2">
              {points.map((point, i) => {
                const ratio = max > 0 && point.y != null ? point.y / max : 0;
                const runLabel = runs[i]?.run_id.slice(0, 8) ?? String(i + 1);
                return (
                  <div key={i} className="flex flex-col items-center gap-1 min-w-0">
                    <span className="text-[10px] text-muted-2 truncate max-w-[48px]">
                      {point.y != null ? formatMetric(point.y, metric.format) : "—"}
                    </span>
                    <div
                      className="w-8 bg-accent/25 rounded-sm"
                      style={{ height: `${Math.max(4, Math.round(ratio * 48))}px` }}
                    />
                    <span
                      className="text-[10px] text-muted-2 truncate max-w-[48px]"
                      title={runs[i]?.run_id}
                    >
                      {runLabel}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SeriesCharts({
  runs,
  metricDefs,
  endpoint,
  hashContent,
}: {
  runs: RunSummary[];
  metricDefs: MetricDef[];
  endpoint: { metrics: Record<string, { series: Array<{ run_id: string; started_at: number; value: number | null }> }> } | undefined;
  hashContent: string;
}) {
  const filtered = metricDefs.filter((metric) => {
    const points = seriesPoints(runs, metric.key, endpoint?.metrics[metric.key]?.series);
    const distinct = new Set(points.map((p) => p.y).filter((v) => v != null));
    return distinct.size >= 2;
  });
  return (
    <PanelGrid cols={2}>
      {filtered.map((metric) => {
        const points = seriesPoints(runs, metric.key, endpoint?.metrics[metric.key]?.series);
        const p50 = median(
          points.map((point) => point.y).filter((value): value is number => value != null),
        );
        return (
          <PanelCard
            key={metric.key}
            title={metric.label}
            eyebrow={metric.source}
            bodyMinHeight={240}
          >
            <MetricSeriesChart
              points={points}
              identity={hashContent}
              height={210}
              formatY={(n) => formatMetric(n, metric.format)}
              reference={p50 != null ? { y: p50, label: "group p50" } : undefined}
              xLabel="invocation"
            />
          </PanelCard>
        );
      })}
    </PanelGrid>
  );
}

function allMetricDefs(
  runs: RunSummary[],
  endpointKeys: string[],
  agentPath: string | null,
): MetricDef[] {
  const names = new Set([...BUILT_INS.map((metric) => metric.key), ...endpointKeys]);
  for (const run of runs) {
    for (const key of Object.keys(run.metrics ?? {})) names.add(key);
  }
  return [...names].map((key) => {
    const builtin = BUILT_INS.find((metric) => metric.key === key);
    if (builtin) return builtin;
    return {
      key,
      label: key,
      format: metricFormat(key),
      source: agentPath ?? "user",
    };
  });
}

function seriesPoints(
  runs: RunSummary[],
  key: string,
  endpointSeries: Array<{ run_id: string; started_at: number; value: number | null }> | undefined,
) {
  if (endpointSeries && endpointSeries.length > 0) {
    return [...endpointSeries]
      .sort((a, b) => a.started_at - b.started_at)
      .map((point, index) => ({ x: index + 1, y: point.value, runId: point.run_id }));
  }
  return runs.map((run, index) => ({
    x: index + 1,
    y: runMetric(run, key, runs, index),
    runId: run.run_id,
  }));
}

function scatterPoints(runs: RunSummary[], key: "cost_usd" | "tokens") {
  return runs.map((run) => ({
    x: run.duration_ms,
    y:
      key === "cost_usd"
        ? (run.cost?.cost_usd ?? null)
        : run.prompt_tokens + run.completion_tokens,
  }));
}

function runMetric(run: RunSummary, key: string, runs: RunSummary[], index: number): number | null {
  switch (key) {
    case "latency_ms":
      return run.duration_ms;
    case "prompt_tokens":
      return run.prompt_tokens;
    case "completion_tokens":
      return run.completion_tokens;
    case "cost_usd":
      return run.cost?.cost_usd ?? null;
    case "error_rate":
      return rollingAverage(runs, index, (item) => (item.state === "error" ? 1 : 0));
    case "schema_validation_rate":
      return run.hash_output_schema ? 1 : null;
    default:
      return run.metrics?.[key] ?? null;
  }
}

function rollingAverage(
  runs: RunSummary[],
  index: number,
  read: (run: RunSummary) => number,
): number {
  const window = runs.slice(Math.max(0, index - 4), index + 1);
  return window.reduce((acc, run) => acc + read(run), 0) / Math.max(window.length, 1);
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? (sorted[mid] ?? null)
    : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
}

function metricFormat(key: string): MetricDef["format"] {
  if (key.includes("latency") || key.endsWith("_ms")) return "ms";
  if (key.includes("token")) return "tokens";
  if (key.includes("cost") || key.includes("usd")) return "cost";
  if (key.includes("score") || key.includes("match") || key.includes("rate")) return "score";
  return "number";
}

function formatMetric(value: number, format: MetricDef["format"]): string {
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
