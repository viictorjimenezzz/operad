import { ConvergenceCurve } from "@/components/charts/convergence-curve";
import { EmptyState } from "@/components/ui";
import { AlgoEventEnvelope, IterationsResponse, RunEventsResponse } from "@/lib/types";
import { z } from "zod";

type ScorePoint = {
  iterIndex: number;
  score: number | null;
  prevBest: number | null;
};

export function OPROScoreCurveTab({
  dataIterations,
  dataEvents,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
}) {
  const series = buildScoreSeries(dataIterations, dataEvents);
  if (series.iterations.length === 0) {
    return (
      <EmptyState
        title="no score curve yet"
        description="OPRO emits score points after evaluate iterations run"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <ConvergenceCurve data={series} height={280} />
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

function buildScoreSeries(dataIterations: unknown, dataEvents: unknown): {
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

function eventPoints(dataEvents: unknown): ScorePoint[] {
  const parsed = RunEventsResponse.safeParse(dataEvents);
  if (!parsed.success) return [];

  return parsed.data.events
    .filter((event): event is z.infer<typeof AlgoEventEnvelope> => event.type === "algo_event")
    .filter((event) => event.kind === "iteration" && event.algorithm_path === "OPRO")
    .map((event) => ({
      iterIndex: numberValue(event.payload.iter_index) ?? numberValue(event.payload.step_index) ?? 0,
      score: numberValue(event.payload.score),
      prevBest: numberValue(event.payload.prev_best),
    }))
    .sort((a, b) => a.iterIndex - b.iterIndex);
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export const _oproScoreCurve = {
  buildScoreSeries,
};
