import { OPROScoreCurveTab, _oproScoreCurve } from "@/components/algorithms/opro/score-curve-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("OPROScoreCurveTab", () => {
  it("marks iterations that improved over prev_best", () => {
    const series = _oproScoreCurve.buildScoreSeries(iterations, undefined);
    expect(series.improvements.map((point) => point.iterIndex)).toEqual([2, 4]);
  });

  it("renders convergence curve and improvement chips", () => {
    render(<OPROScoreCurveTab dataIterations={iterations} />);
    expect(screen.getByText("improvements")).toBeTruthy();
    expect(screen.queryByText("none")).toBeNull();
    expect(document.querySelector(".recharts-responsive-container")).toBeTruthy();
  });

  it("builds tracking metrics from OPROOptimizer iteration payloads", () => {
    const metrics = _oproScoreCurve.buildMetricSeries(undefined, metricEvents);
    expect(metrics.map((metric) => metric.key)).toEqual(["length_max", "length_mean"]);
    expect(metrics.find((metric) => metric.key === "length_mean")?.points).toEqual([
      { x: 1, y: 240, runId: "opro-run" },
      { x: 2, y: 260, runId: "opro-run" },
    ]);
  });

  it("renders tracking metric cards", () => {
    render(<OPROScoreCurveTab dataEvents={metricEvents} />);
    expect(screen.getByText("Tracking metrics")).toBeTruthy();
    expect(screen.getByText("length_mean")).toBeTruthy();
    expect(screen.getByText("length_max")).toBeTruthy();
  });
});

const iterations = {
  iterations: [
    { iter_index: 1, score: 0.2, phase: "evaluate", text: null, metadata: { prev_best: 0.3 } },
    { iter_index: 2, score: 0.5, phase: "evaluate", text: null, metadata: { prev_best: 0.4 } },
    { iter_index: 3, score: 0.45, phase: "evaluate", text: null, metadata: { prev_best: 0.5 } },
    { iter_index: 4, score: 0.61, phase: "evaluate", text: null, metadata: { prev_best: 0.5 } },
  ],
  max_iter: 4,
  threshold: null,
  converged: null,
};

const metricEvents = {
  run_id: "opro-run",
  events: [
    iterationEvent(1, 0.4, { length_mean: 240 }, { length_max: 301 }),
    iterationEvent(2, 0.6, { length_mean: 260 }, { length_max: 318 }),
  ],
};

function iterationEvent(
  stepIndex: number,
  score: number,
  metrics: Record<string, number>,
  extra: Record<string, number>,
) {
  return {
    type: "algo_event",
    run_id: "opro-run",
    algorithm_path: "OPROOptimizer",
    kind: "iteration",
    payload: {
      iter_index: stepIndex,
      step_index: stepIndex,
      phase: "evaluate",
      param_path: "task",
      candidate_value: `candidate ${stepIndex}`,
      score,
      metrics,
      ...extra,
    },
    started_at: stepIndex,
    finished_at: stepIndex,
    metadata: {},
  };
}
