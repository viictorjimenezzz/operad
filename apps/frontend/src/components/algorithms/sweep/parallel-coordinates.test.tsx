import { ParallelCoordinates } from "@/components/algorithms/sweep/parallel-coordinates";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("ParallelCoordinates", () => {
  it("falls back for low-dimensional sweeps", () => {
    render(
      <ParallelCoordinates
        data={{
          cells: [{ cell_index: 0, parameters: {}, score: null }],
          axes: [],
          score_range: null,
          best_cell_index: null,
          total_cells: 1,
          finished: true,
        }}
      />,
    );
    expect(screen.getByText("parallel coordinates unavailable")).toBeTruthy();
  });

  it("renders an svg plot for 3d sweeps", () => {
    const { container } = render(
      <ParallelCoordinates
        data={{
          cells: [
            { cell_index: 0, parameters: { a: 1, b: "x", c: true }, score: 0.4 },
            { cell_index: 1, parameters: { a: 2, b: "y", c: false }, score: 0.8 },
          ],
          axes: [
            { name: "a", values: [1, 2] },
            { name: "b", values: ["x", "y"] },
            { name: "c", values: [false, true] },
          ],
          score_range: [0.4, 0.8],
          best_cell_index: 1,
          total_cells: 2,
          finished: true,
        }}
      />,
    );

    expect(container.querySelector("svg[aria-label='parallel coordinates']")).toBeTruthy();
  });
});
