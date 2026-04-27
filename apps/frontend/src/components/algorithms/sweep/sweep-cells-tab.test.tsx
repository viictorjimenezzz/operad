import { SweepCellsTab } from "@/components/algorithms/sweep/sweep-cells-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("SweepCellsTab", () => {
  it("renders one dynamic column per sweep axis", () => {
    render(
      <MemoryRouter>
        <SweepCellsTab
          runId="sweep-1"
          data={{
            cells: [
              {
                cell_index: 0,
                parameters: { temperature: 0.2, model: "mini" },
                score: 0.7,
              },
            ],
            axes: [
              { name: "temperature", values: [0.2] },
              { name: "model", values: ["mini"] },
            ],
            score_range: [0.7, 0.7],
            best_cell_index: 0,
            total_cells: 1,
            finished: true,
          }}
          dataChildren={[
            {
              run_id: "child-1",
              started_at: 1,
              last_event_at: 2,
              state: "ended",
              has_graph: false,
              is_algorithm: false,
              algorithm_path: null,
              root_agent_path: "Reasoner",
              event_counts: {},
              event_total: 1,
              duration_ms: 100,
              generations: [],
              iterations: [],
              rounds: [],
              candidates: [],
              batches: [],
              prompt_tokens: 1,
              completion_tokens: 1,
              error: null,
              algorithm_terminal_score: null,
            },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("temperature")).toBeTruthy();
    expect(screen.getByText("model")).toBeTruthy();
    expect(screen.getByText("mini")).toBeTruthy();
  });
});
