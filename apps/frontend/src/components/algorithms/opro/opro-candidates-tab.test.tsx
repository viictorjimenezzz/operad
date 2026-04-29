import { OPROCandidatesTab } from "@/components/algorithms/opro/opro-candidates-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("OPROCandidatesTab", () => {
  it("renders sortable candidate rows with the required storage key shape", () => {
    render(
      <MemoryRouter>
        <OPROCandidatesTab runId="opro-run" dataEvents={events} dataChildren={[]} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Step")).toBeTruthy();
    expect(screen.getByText("Score")).toBeTruthy();
    expect(screen.getByText("accepted")).toBeTruthy();
    expect(screen.getByText("rejected")).toBeTruthy();
    expect(screen.getByText(/clear factual answer/)).toBeTruthy();
    expect(
      window.localStorage.getItem("operad.dashboard.runtable.cols.opro-candidates:opro-run"),
    ).toBeNull();
  });
});

const events = {
  run_id: "opro-run",
  events: [
    iteration(1, "Write a clear factual answer.", 0.84, true),
    iteration(2, "Write a short answer.", 0.71, false),
  ],
};

function iteration(step: number, candidateValue: string, score: number, accepted: boolean) {
  return {
    type: "algo_event",
    run_id: "opro-run",
    algorithm_path: "OPROOptimizer",
    kind: "iteration",
    payload: {
      iter_index: step,
      step_index: step,
      phase: "evaluate",
      param_path: "rules",
      candidate_value: candidateValue,
      score,
      accepted,
    },
    started_at: step,
    finished_at: step,
    metadata: {},
  };
}
