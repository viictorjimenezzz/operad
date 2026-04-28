import {
  OPROScoreCurveTab,
  _oproScoreCurve,
} from "@/components/algorithms/opro/score-curve-tab";
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
