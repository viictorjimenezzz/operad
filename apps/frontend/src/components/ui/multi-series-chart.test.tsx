import { MultiSeriesChart } from "@/components/ui/multi-series-chart";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("MultiSeriesChart", () => {
  it("renders a circle marker for single-point series and a path for multi-point series", () => {
    const { container } = render(
      <MultiSeriesChart
        series={[
          { id: "single", points: [{ x: 0, y: 1 }] },
          {
            id: "line",
            points: [
              { x: 0, y: 1 },
              { x: 1, y: 2 },
            ],
          },
        ]}
      />,
    );

    expect(container.querySelector("circle")).toBeTruthy();
    expect(container.querySelector("path")?.getAttribute("d")).toContain("L");
  });
});
