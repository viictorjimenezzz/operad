import { SweepCellsTab } from "@/components/algorithms/sweep/sweep-cells-tab";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

  it("shows compare CTA when two sweep cells are selected", () => {
    const { container } = render(
      <MemoryRouter>
        <SweepCellsTab
          runId="sweep-1"
          data={{
            cells: [
              { cell_index: 0, parameters: { temperature: 0.2 }, score: 0.7 },
              { cell_index: 1, parameters: { temperature: 0.4 }, score: 0.9 },
            ],
            axes: [{ name: "temperature", values: [0.2, 0.4] }],
            score_range: [0.7, 0.9],
            best_cell_index: 1,
            total_cells: 2,
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
            {
              run_id: "child-2",
              started_at: 2,
              last_event_at: 3,
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

    const toggles = container.querySelectorAll('button[aria-label^="select "]');
    expect(toggles.length).toBeGreaterThanOrEqual(2);
    fireEvent.click(toggles[0] as HTMLButtonElement);
    fireEvent.click(toggles[1] as HTMLButtonElement);

    expect(screen.getByText("2 selected")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Compare" })).toBeTruthy();
  });
});
