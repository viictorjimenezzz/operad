import { ConvergenceCurve } from "@/components/charts/convergence-curve";
import { EmptyState, MetricSeriesChart, PanelCard, PanelGrid, PanelSection } from "@/components/ui";
import { type AlgoEventEnvelope, IterationsResponse, RunEventsResponse } from "@/lib/types";
import { formatNumber } from "@/lib/utils";
import type { z } from "zod";

type ScorePoint = {
  iterIndex: number;
  score: number | null;
  prevBest: number | null;
};

type MetricSeries = {
  key: string;
  points: Array<{ x: number; y: number | null; runId: string }>;
};

const STRUCTURAL_METRIC_KEYS = new Set([
  "accepted",
  "candidate_index",
  "history_size",
  "iter_index",
  "phase",
  "score",
  "step_index",
]);

export function OPROScoreCurveTab({
  dataIterations,
  dataEvents,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
}) {
  const metrics = buildMetricSeries(dataIterations, dataEvents);

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto max-w-[1280px] space-y-4">
        <PanelSection label="Objective">
          <PanelCard title="Score" eyebrow="accepted candidate objective" bodyMinHeight={260}>
            <OPROScorePanel dataIterations={dataIterations} dataEvents={dataEvents} />
          </PanelCard>
        </PanelSection>
        <PanelSection label="Tracking metrics" count={metrics.length}>
          {metrics.length > 0 ? (
            <PanelGrid cols={3}>
              {metrics.map((metric) => (
                <MetricCard key={metric.key} metric={metric} />
              ))}
            </PanelGrid>
          ) : (
            <EmptyState
              title="no tracking metrics"
              description="numeric OPRO tracking metrics appear after evaluate events emit metric payloads"
              className="min-h-40"
            />
          )}
        </PanelSection>
      </div>
    </div>
  );
}

export function OPROScorePanel({
  dataIterations,
  dataEvents,
  compact = false,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
  compact?: boolean;
}) {
  const series = buildScoreSeries(dataIterations, dataEvents);
  const distinctIterCount = new Set(series.iterations.map((it) => it.iter_index)).size;

  if (series.iterations.length === 0) {
    return (
      <EmptyState
        title="no score curve yet"
        description="OPRO emits score points after evaluate iterations run"
        {...(compact ? { className: "min-h-40" } : {})}
      />
    );
  }

  if (distinctIterCount < 2) {
    const single = series.iterations.find((it) => it.score != null) ?? series.iterations[0];
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded border border-border bg-bg-inset px-6 py-8 text-center">
        <div className="text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2">
          single iteration
        </div>
        <div className="text-[18px] font-semibold tabular-nums text-text">
          {single?.score == null ? "—" : single.score.toFixed(3)}
        </div>
        <p className="m-0 max-w-md text-[12px] text-muted">
          A score curve appears once at least two evaluate iterations have landed.
        </p>
      </div>
    );
  }

  return (
    <div>
      <ConvergenceCurve data={series} height={compact ? 220 : 280} />
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <span className="font-medium text-text">improvements</span>
        {series.improvements.length > 0 ? (
          series.improvements.map((point) => (
            <span
              key={`improved-${point.iterIndex}`}
              className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 font-mono text-text"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-ok" aria-hidden="true" />
              {point.iterIndex}
            </span>
          ))
        ) : (
          <span className="text-muted-2">none</span>
        )}
      </div>
    </div>
  );
}

function MetricCard({ metric }: { metric: MetricSeries }) {
  const values = metric.points
    .map((point) => point.y)
    .filter((value): value is number => value != null && Number.isFinite(value));
  const latest = [...metric.points].reverse().find((point) => point.y != null)?.y ?? null;
  const distinct = new Set(values).size;
  const hasSeries = values.length >= 2 && distinct >= 2;

  return (
    <PanelCard
      title={metric.key}
      eyebrow={`${values.length} sample${values.length === 1 ? "" : "s"}`}
      bodyMinHeight={220}
    >
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.06em] text-muted-2">latest</div>
          <div className="mt-0.5 font-mono text-[18px] text-text">{formatMetric(latest)}</div>
        </div>
        <div className="text-right text-[11px] text-muted">
          <div>min {formatMetric(values.length > 0 ? Math.min(...values) : null)}</div>
          <div>max {formatMetric(values.length > 0 ? Math.max(...values) : null)}</div>
        </div>
      </div>
      {hasSeries ? (
        <MetricSeriesChart
          points={metric.points}
          identity={`opro:${metric.key}`}
          height={130}
          formatY={formatMetric}
          xLabel="step"
        />
      ) : values.length > 0 ? (
        <div className="flex h-[130px] items-center justify-between rounded border border-border bg-bg-inset px-3 text-[12px] text-muted">
          <span>{distinct === 1 ? "constant" : "limited samples"}</span>
          <span className="font-mono text-text">{formatMetric(latest)}</span>
        </div>
      ) : (
        <div className="flex h-[130px] items-center justify-center rounded border border-border bg-bg-inset text-[12px] text-muted-2">
          no numeric samples
        </div>
      )}
    </PanelCard>
  );
}

function buildScoreSeries(
  dataIterations: unknown,
  dataEvents: unknown,
): {
  iterations: Array<{ iter_index: number; score: number | null }>;
  threshold: number | null;
  converged: boolean | null;
  improvements: ScorePoint[];
} {
  const parsedIterations = IterationsResponse.safeParse(dataIterations);
  const fromIterations = parsedIterations.success
    ? parsedIterations.data.iterations
        .map((iteration) => ({
          iterIndex: iteration.iter_index,
          score: iteration.score,
          prevBest: numberValue(iteration.metadata.prev_best),
        }))
        .sort((a, b) => a.iterIndex - b.iterIndex)
    : [];

  const fromEvents = eventPoints(dataEvents);
  const points = fromIterations.length > 0 ? fromIterations : fromEvents;

  return {
    iterations: points.map((point) => ({ iter_index: point.iterIndex, score: point.score })),
    threshold: parsedIterations.success ? parsedIterations.data.threshold : null,
    converged: parsedIterations.success ? parsedIterations.data.converged : null,
    improvements: points.filter(
      (point) =>
        point.score != null &&
        point.prevBest != null &&
        Number.isFinite(point.score) &&
        Number.isFinite(point.prevBest) &&
        point.score > point.prevBest,
    ),
  };
}

function buildMetricSeries(dataIterations: unknown, dataEvents: unknown): MetricSeries[] {
  const rows = metricRowsFromEvents(dataEvents);
  if (rows.length === 0) rows.push(...metricRowsFromIterations(dataIterations));

  const byKey = new Map<string, Map<number, { y: number; runId: string }>>();
  for (const row of rows) {
    const points = byKey.get(row.key) ?? new Map<number, { y: number; runId: string }>();
    points.set(row.stepIndex, { y: row.value, runId: row.runId });
    byKey.set(row.key, points);
  }

  return [...byKey.entries()]
    .map(([key, points]) => ({
      key,
      points: [...points.entries()]
        .sort(([a], [b]) => a - b)
        .map(([stepIndex, point]) => ({ x: stepIndex, y: point.y, runId: point.runId })),
    }))
    .sort((a, b) => a.key.localeCompare(b.key));
}

function eventPoints(dataEvents: unknown): ScorePoint[] {
  const parsed = RunEventsResponse.safeParse(dataEvents);
  if (!parsed.success) return [];

  return parsed.data.events
    .filter((event): event is z.infer<typeof AlgoEventEnvelope> => event.type === "algo_event")
    .filter((event) => event.kind === "iteration" && isOPROAlgorithm(event.algorithm_path))
    .map((event) => ({
      iterIndex:
        numberValue(event.payload.iter_index) ?? numberValue(event.payload.step_index) ?? 0,
      score: numberValue(event.payload.score),
      prevBest: numberValue(event.payload.prev_best),
    }))
    .sort((a, b) => a.iterIndex - b.iterIndex);
}

function metricRowsFromEvents(dataEvents: unknown): Array<{
  key: string;
  stepIndex: number;
  runId: string;
  value: number;
}> {
  const parsed = RunEventsResponse.safeParse(dataEvents);
  if (!parsed.success) return [];
  const rows: Array<{ key: string; stepIndex: number; runId: string; value: number }> = [];
  for (const event of parsed.data.events) {
    if (event.type !== "algo_event") continue;
    if (event.kind !== "iteration" || !isOPROAlgorithm(event.algorithm_path)) continue;
    const stepIndex =
      numberValue(event.payload.step_index) ?? numberValue(event.payload.iter_index) ?? 0;
    rows.push(...numericMetricRows(event.payload, event.metadata, stepIndex, event.run_id));
  }
  return rows;
}

function metricRowsFromIterations(dataIterations: unknown): Array<{
  key: string;
  stepIndex: number;
  runId: string;
  value: number;
}> {
  const parsed = IterationsResponse.safeParse(dataIterations);
  if (!parsed.success) return [];
  const rows: Array<{ key: string; stepIndex: number; runId: string; value: number }> = [];
  for (const iteration of parsed.data.iterations) {
    const stepIndex = numberValue(iteration.metadata.step_index) ?? iteration.iter_index;
    rows.push(...numericMetricRows(iteration.metadata, {}, stepIndex, "iterations"));
  }
  return rows;
}

function numericMetricRows(
  payload: Record<string, unknown>,
  metadata: Record<string, unknown>,
  stepIndex: number,
  runId: string,
): Array<{ key: string; stepIndex: number; runId: string; value: number }> {
  const rows: Array<{ key: string; stepIndex: number; runId: string; value: number }> = [];
  collectNumericMetrics(rows, payload, stepIndex, runId);
  collectNumericMetrics(rows, recordValue(payload.metrics), stepIndex, runId);
  collectNumericMetrics(rows, recordValue(metadata.metrics), stepIndex, runId);
  return rows;
}

function collectNumericMetrics(
  rows: Array<{ key: string; stepIndex: number; runId: string; value: number }>,
  source: Record<string, unknown>,
  stepIndex: number,
  runId: string,
) {
  for (const [key, value] of Object.entries(source)) {
    if (STRUCTURAL_METRIC_KEYS.has(key)) continue;
    if (typeof value !== "number" || !Number.isFinite(value)) continue;
    rows.push({ key, stepIndex, runId, value });
  }
}

function recordValue(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatMetric(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (Math.abs(value) <= 1) return value.toFixed(3);
  return formatNumber(value);
}

function isOPROAlgorithm(path: string | null | undefined): boolean {
  return path === "OPRO" || path === "OPROOptimizer";
}

export const _oproScoreCurve = {
  buildScoreSeries,
  buildMetricSeries,
};
