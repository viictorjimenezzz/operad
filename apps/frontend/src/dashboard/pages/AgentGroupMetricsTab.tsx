import {
  MetricSeriesChart,
  MultiSeriesChart,
  PanelCard,
  PanelGrid,
  PanelSection,
} from "@/components/ui";
import { useAgentGroup, useAgentGroupMetrics } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { cn, formatCost, formatDurationMs, formatNumber, formatTokens } from "@/lib/utils";
import { useParams } from "react-router-dom";

type MetricFormat = "ms" | "tokens" | "cost" | "score" | "number";

type MetricDef = {
  key: string;
  label: string;
  format: MetricFormat;
  source: string;
  unit: string | null;
};

type MetricPoint = { x: number; y: number | null; runId: string };

type EndpointMetrics = {
  metrics: Record<
    string,
    {
      unit?: string | null;
      series: Array<{ run_id: string; started_at: number; value: number | null }>;
    }
  >;
};

const BUILT_INS: MetricDef[] = [
  { key: "latency_ms", label: "Latency", format: "ms", source: "built-in", unit: "ms" },
  {
    key: "prompt_tokens",
    label: "Prompt tokens",
    format: "tokens",
    source: "built-in",
    unit: "tokens",
  },
  {
    key: "completion_tokens",
    label: "Completion tokens",
    format: "tokens",
    source: "built-in",
    unit: "tokens",
  },
  { key: "cost_usd", label: "Cost", format: "cost", source: "built-in", unit: "usd" },
  { key: "error_rate", label: "Error rate", format: "score", source: "built-in", unit: null },
  {
    key: "schema_validation_rate",
    label: "Output schema validation",
    format: "score",
    source: "built-in",
    unit: null,
  },
];

export function AgentGroupMetricsTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const endpoint = useAgentGroupMetrics(hashContent);

  if (!hashContent || !group.data) return null;
  const runs = [...group.data.runs].sort((a, b) => a.started_at - b.started_at);
  const agentPath = runs.at(-1)?.root_agent_path ?? null;
  const metricDefs = allMetricDefs(
    runs,
    endpoint.data?.metrics ? Object.keys(endpoint.data.metrics) : [],
    endpoint.data as EndpointMetrics | undefined,
    agentPath,
  );

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto max-w-[1280px] space-y-4">
        {runs.length >= 2 ? (
          <PanelSection label="Relationships">
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
          <PanelGrid cols={3}>
            {metricDefs.map((metric) => (
              <MetricCard
                key={metric.key}
                metric={metric}
                runs={runs}
                endpoint={endpoint.data as EndpointMetrics | undefined}
                hashContent={hashContent}
              />
            ))}
          </PanelGrid>
        </PanelSection>
      </div>
    </div>
  );
}

function MetricCard({
  metric,
  runs,
  endpoint,
  hashContent,
}: {
  metric: MetricDef;
  runs: RunSummary[];
  endpoint: EndpointMetrics | undefined;
  hashContent: string;
}) {
  const points = seriesPoints(runs, metric.key, endpoint?.metrics[metric.key]?.series);
  const values = points.map((point) => point.y).filter((value): value is number => value != null);
  const latest = [...points].reverse().find((point) => point.y != null)?.y ?? null;
  const p50 = median(values);
  const min = values.length > 0 ? Math.min(...values) : null;
  const max = values.length > 0 ? Math.max(...values) : null;
  const distinct = new Set(values).size;
  const hasSeries = values.length >= 2 && distinct >= 2;

  return (
    <PanelCard
      title={metric.label}
      eyebrow={metric.source}
      bodyMinHeight={240}
      toolbar={
        metric.unit ? (
          <span className="rounded border border-border bg-bg-inset px-1.5 py-0.5 font-mono text-[10px] text-muted-2">
            {metric.unit}
          </span>
        ) : null
      }
    >
      <div className="mb-3 grid grid-cols-[minmax(0,1fr)_auto] gap-3">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-[0.06em] text-muted-2">latest</div>
          <div className="mt-0.5 truncate font-mono text-[18px] text-text">
            {formatMetric(latest, metric.format)}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 text-right">
          <MetricStat label="p50" value={formatMetric(p50, metric.format)} />
          <MetricStat label="min" value={formatMetric(min, metric.format)} />
          <MetricStat label="max" value={formatMetric(max, metric.format)} />
        </div>
      </div>
      {hasSeries ? (
        <MetricSeriesChart
          points={points}
          identity={hashContent}
          height={145}
          formatY={(n) => formatMetric(n, metric.format)}
          reference={p50 != null ? { y: p50, label: "p50" } : undefined}
          xLabel="invocation"
        />
      ) : values.length > 0 ? (
        <ConstantMetricPreview value={latest} values={values} format={metric.format} />
      ) : (
        <NoDataPreview />
      )}
    </PanelCard>
  );
}

function MetricStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.06em] text-muted-2">{label}</div>
      <div className="mt-0.5 font-mono text-[11px] text-muted">{value}</div>
    </div>
  );
}

function ConstantMetricPreview({
  value,
  values,
  format,
}: {
  value: number | null;
  values: number[];
  format: MetricFormat;
}) {
  const label = value == null ? "—" : formatMetric(value, format);
  return (
    <div className="rounded-md border border-border bg-bg-inset p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-[12px] text-muted">
          {new Set(values).size === 1 ? "constant across invocations" : "limited samples"}
        </span>
        <span className="font-mono text-[12px] text-text">{label}</span>
      </div>
      <div className="flex h-20 items-end gap-1">
        {values.map((point, index) => (
          <div
            key={`${point}:${index}`}
            className={cn(
              "min-w-1 flex-1 rounded-t-sm bg-accent/25",
              point === 0 && "bg-accent/15",
            )}
            style={{ height: `${point === 0 ? 10 : 38}px` }}
            title={formatMetric(point, format)}
          />
        ))}
      </div>
    </div>
  );
}

function NoDataPreview() {
  return (
    <div className="flex h-[118px] items-center justify-center rounded-md border border-border bg-bg-inset text-[12px] text-muted-2">
      no numeric samples
    </div>
  );
}

function allMetricDefs(
  runs: RunSummary[],
  endpointKeys: string[],
  endpoint: EndpointMetrics | undefined,
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
      unit: endpoint?.metrics[key]?.unit ?? null,
    };
  });
}

function seriesPoints(
  runs: RunSummary[],
  key: string,
  endpointSeries: Array<{ run_id: string; started_at: number; value: number | null }> | undefined,
): MetricPoint[] {
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
      key === "cost_usd" ? (run.cost?.cost_usd ?? null) : run.prompt_tokens + run.completion_tokens,
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

function metricFormat(key: string): MetricFormat {
  if (key.includes("latency") || key.endsWith("_ms")) return "ms";
  if (key.includes("token")) return "tokens";
  if (key.includes("cost") || key.includes("usd")) return "cost";
  if (key.includes("score") || key.includes("match") || key.includes("rate")) return "score";
  return "number";
}

function formatMetric(value: number | null, format: MetricFormat): string {
  if (value == null || !Number.isFinite(value)) return "—";
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
