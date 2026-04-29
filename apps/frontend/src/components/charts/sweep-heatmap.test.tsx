import { SweepHeatmap } from "@/components/charts/sweep-heatmap";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("SweepHeatmap", () => {
  it("renders scored matrix cells", () => {
    render(
      <SweepHeatmap
        data={{
          cells: [
            { cell_index: 0, parameters: { prompt: "short", temperature: 0 }, score: 0.4 },
            { cell_index: 1, parameters: { prompt: "short", temperature: 1 }, score: 0.8 },
          ],
          axes: [
            { name: "prompt", values: ["short"] },
            { name: "temperature", values: [0, 1] },
          ],
          score_range: [0.4, 0.8],
          best_cell_index: 1,
          total_cells: 2,
          finished: true,
        }}
      />,
    );

    expect(screen.getByText("0.400")).toBeTruthy();
    expect(screen.getByText("0.800")).toBeTruthy();
    expect(screen.queryByText(/did not define a score function/)).toBeNull();
  });
});
