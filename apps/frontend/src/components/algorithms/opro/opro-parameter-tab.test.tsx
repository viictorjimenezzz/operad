import { OPROParameterTab, _oproParameter } from "@/components/algorithms/opro/opro-parameter-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("OPROParameterTab", () => {
  it("builds one accepted-value lane per optimized parameter", () => {
    const series = _oproParameter.buildParameterSeries([
      step(1, "rules", "first accepted", 0.6, true),
      step(2, "rules", "rejected", 0.5, false),
      step(3, "rules", "second accepted", 0.8, true),
      step(4, "task", "task accepted", 0.7, true),
    ]);

    expect(series).toHaveLength(2);
    expect(series.find((item) => item.path === "rules")?.points).toHaveLength(2);
    expect(series.find((item) => item.path === "task")?.points).toHaveLength(1);
  });

  it("renders lane evolution with a diff against the previous accepted value", () => {
    render(<OPROParameterTab dataEvents={events} />);

    expect(screen.getByText("rules")).toBeTruthy();
    expect(screen.getByText(/2 distinct values accepted/)).toBeTruthy();
    expect(screen.getAllByText("first accepted").length).toBeGreaterThan(0);
    expect(screen.getAllByText("second accepted").length).toBeGreaterThan(0);
    expect(screen.getByText("step 1")).toBeTruthy();
    expect(screen.getAllByText("step 2").length).toBeGreaterThan(0);
  });
});

const events = {
  run_id: "opro-run",
  events: [iteration(1, "first accepted", 0.6, true), iteration(2, "second accepted", 0.8, true)],
};

function iteration(stepIndex: number, candidateValue: string, score: number, accepted: boolean) {
  return {
    type: "algo_event",
    run_id: "opro-run",
    algorithm_path: "OPRO",
    kind: "iteration",
    payload: {
      iter_index: stepIndex,
      step_index: stepIndex,
      phase: "evaluate",
      param_path: "rules",
      candidate_value: candidateValue,
      score,
      accepted,
    },
    started_at: stepIndex,
    finished_at: stepIndex,
    metadata: {},
  };
}

function step(
  stepIndex: number,
  paramPath: string,
  candidateValue: string,
  score: number,
  accepted: boolean,
) {
  return {
    iterIndex: stepIndex,
    stepIndex,
    paramPath,
    candidateValue,
    historySize: null,
    score,
    accepted,
    proposedAt: null,
    evaluatedAt: stepIndex,
    proposerRun: null,
    evaluatorRun: null,
  };
}
