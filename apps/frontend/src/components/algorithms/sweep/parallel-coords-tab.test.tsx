import { SweepParallelCoordsTab } from "@/components/algorithms/sweep/parallel-coords-tab";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("SweepParallelCoordsTab", () => {
  it("renders one polyline per cell", () => {
    const { container } = render(
      <MemoryRouter>
        <SweepParallelCoordsTab
          data={{
            cells: [
              { cell_index: 0, parameters: { a: 1, b: "x", c: true }, score: 0.1 },
              { cell_index: 1, parameters: { a: 2, b: "x", c: false }, score: 0.2 },
              { cell_index: 2, parameters: { a: 3, b: "y", c: true }, score: 0.3 },
              { cell_index: 3, parameters: { a: 1, b: "y", c: false }, score: 0.4 },
              { cell_index: 4, parameters: { a: 2, b: "x", c: true }, score: 0.5 },
              { cell_index: 5, parameters: { a: 3, b: "y", c: false }, score: 0.6 },
            ],
            axes: [
              { name: "a", values: [1, 2, 3] },
              { name: "b", values: ["x", "y"] },
              { name: "c", values: [false, true] },
            ],
            score_range: [0.1, 0.6],
            best_cell_index: 5,
            total_cells: 6,
            finished: true,
          }}
        />
      </MemoryRouter>,
    );

    expect(container.querySelectorAll("polyline[data-cell-line='true']")).toHaveLength(6);
  });

  it("shows hovered cell axis values", () => {
    const { container } = render(
      <MemoryRouter>
        <SweepParallelCoordsTab
          data={{
            cells: [{ cell_index: 0, parameters: { temperature: 0.3, model: "mini" }, score: 0.7 }],
            axes: [
              { name: "temperature", values: [0.1, 0.3] },
              { name: "model", values: ["mini", "pro"] },
            ],
            score_range: [0.7, 0.7],
            best_cell_index: 0,
            total_cells: 1,
            finished: true,
          }}
        />
      </MemoryRouter>,
    );

    const line = container.querySelector("polyline[data-cell-line='true']");
    expect(line).toBeTruthy();
    fireEvent.mouseEnter(line!);
    expect(screen.getByText("cell #0")).toBeTruthy();
    expect(screen.getByText("temperature=0.3")).toBeTruthy();
    expect(screen.getByText("model=mini")).toBeTruthy();
  });
});
