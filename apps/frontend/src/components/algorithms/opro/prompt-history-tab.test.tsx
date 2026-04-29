import { OPROPromptHistoryTab } from "@/components/algorithms/opro/prompt-history-tab";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("OPROPromptHistoryTab", () => {
  it("renders history with score curve and prompt diff previews", () => {
    render(
      <MemoryRouter initialEntries={["/algorithms/opro-run"]}>
        <Routes>
          <Route path="/algorithms/:runId" element={<OPROPromptHistoryTab dataEvents={events} />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("iteration 1")).toBeTruthy();
    expect(screen.getByText("iteration 2")).toBeTruthy();
    expect(screen.getByText("improvements")).toBeTruthy();
    expect(screen.getAllByText("first candidate").length).toBeGreaterThan(0);
    expect(screen.getAllByText("second candidate").length).toBeGreaterThan(0);
  });

  it("expands a clicked iteration with stacked prompt panes", () => {
    render(
      <MemoryRouter initialEntries={["/algorithms/opro-run"]}>
        <Routes>
          <Route
            path="/algorithms/:runId"
            element={
              <>
                <OPROPromptHistoryTab dataEvents={events} />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /iteration 2/i }));
    expect(screen.getByTestId("search").textContent).toContain("step=2");
    expect(screen.getByTestId("search").textContent).not.toContain("param=rules");
    expect(screen.getAllByText("previous").length).toBeGreaterThan(0);
    expect(screen.getAllByText("step 2").length).toBeGreaterThan(0);
  });
});

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="search">{location.search}</div>;
}

const events = {
  run_id: "opro-run",
  events: [
    iteration("propose", 1, {
      current_value: "initial prompt",
      candidate_value: "first candidate",
    }),
    iteration("evaluate", 1, { candidate_value: "first candidate", score: 0.41, accepted: true }),
    iteration("propose", 2, {
      current_value: "first candidate",
      candidate_value: "second candidate",
    }),
    iteration("evaluate", 2, {
      candidate_value: "second candidate",
      score: 0.63,
      accepted: true,
    }),
  ],
};

function iteration(
  phase: "propose" | "evaluate",
  iterIndex: number,
  extra: Record<string, unknown>,
) {
  return {
    type: "algo_event",
    run_id: "opro-run",
    algorithm_path: "OPROOptimizer",
    kind: "iteration",
    payload: {
      iter_index: iterIndex,
      step_index: iterIndex,
      phase,
      param_path: "rules",
      ...extra,
    },
    started_at: iterIndex,
    finished_at: phase === "evaluate" ? iterIndex : null,
    metadata: {},
  };
}
