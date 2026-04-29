import { EmptyState } from "@/components/ui/empty-state";
import { MetricSeriesChart } from "@/components/ui/metric-series-chart";
import { beamCandidateDetails, type BeamCandidateDetail } from "@/lib/beam-data";
import { Candidate } from "@/lib/types";
import { formatCost, formatDurationMs } from "@/lib/utils";
import { z } from "zod";

const CandidateArray = z.array(Candidate);

interface BeamMetricsTabProps {
  data: unknown;
  dataIterations?: unknown;
  dataEvents?: unknown;
  dataChildren?: unknown;
  dataAgentsSummary?: unknown;
}

type MetricSpec = {
  key: string;
  label: string;
  value: (detail: BeamCandidateDetail) => number | null;
  format: (value: number) => string;
};

const metricSpecs: MetricSpec[] = [
  {
    key: "score",
    label: "score",
    value: (detail) => detail.candidate.score,
    format: (value) => value.toFixed(3),
  },
  {
    key: "generator-latency",
    label: "generator latency",
    value: (detail) => detail.generatorLatencyMs,
    format: formatDurationMs,
  },
  {
    key: "critic-latency",
    label: "critic latency",
    value: (detail) => detail.criticLatencyMs,
    format: formatDurationMs,
  },
  {
    key: "total-latency",
    label: "total latency",
    value: (detail) => detail.totalLatencyMs,
    format: formatDurationMs,
  },
  {
    key: "cost",
    label: "cost",
    value: (detail) => detail.costUsd,
    format: formatCost,
  },
  {
    key: "prompt-tokens",
    label: "prompt tokens",
    value: (detail) => detail.promptTokens,
    format: (value) => Math.round(value).toString(),
  },
  {
    key: "completion-tokens",
    label: "completion tokens",
    value: (detail) => detail.completionTokens,
    format: (value) => Math.round(value).toString(),
  },
];

export function BeamMetricsTab({
  data,
  dataIterations,
  dataEvents,
  dataChildren,
  dataAgentsSummary,
}: BeamMetricsTabProps) {
  const parsed = CandidateArray.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no beam metrics" description="waiting for candidate metrics" />;
  }

  const details = beamCandidateDetails(
    parsed.data,
    dataIterations,
    dataEvents,
    dataChildren,
    dataAgentsSummary,
  );
  const metrics = metricSpecs
    .map((spec) => ({
      spec,
      points: details.map((detail) => ({
        x: detail.candidateIndex,
        y: spec.value(detail),
        runId: `candidate-${detail.candidateIndex}`,
      })),
    }))
    .filter((metric) =>
      metric.points.some((point) => typeof point.y === "number" && Number.isFinite(point.y)),
    );

  if (metrics.length === 0) {
    return (
      <EmptyState
        title="no beam metrics"
        description="candidate events are present, but no numeric metrics were captured"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {metrics.map(({ spec, points }) => (
          <section key={spec.key} className="rounded-lg border border-border bg-bg-1 p-3">
            <div className="mb-2 text-[13px] font-medium text-text">{spec.label}</div>
            <MetricSeriesChart
              points={points}
              identity={`beam:${spec.key}`}
              height={170}
              formatY={spec.format}
              formatX={(value) => `#${Math.round(value)}`}
              yLabel={spec.label}
              xLabel="candidate"
            />
          </section>
        ))}
      </div>
    </div>
  );
}
