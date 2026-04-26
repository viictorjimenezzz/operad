import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CurveOverlay } from "./curve-overlay";

afterEach(cleanup);

describe("CurveOverlay", () => {
  it("renders empty state without points", () => {
    render(
      <CurveOverlay
        series={[
          { runId: "r1", label: "run 1", points: [] },
          { runId: "r2", label: "run 2", points: [] },
        ]}
      />,
    );
    expect(screen.getByText("no curve data")).toBeTruthy();
  });

  it("renders chart and heterogeneous label", () => {
    const { container } = render(
      <CurveOverlay
        isHeterogeneous
        series={[
          {
            runId: "r1",
            label: "EvoGradient/r1",
            points: [
              { x: 0, y: 0.2 },
              { x: 1, y: 0.4 },
            ],
          },
          {
            runId: "r2",
            label: "Trainer/r2",
            points: [
              { x: 0, y: -0.6 },
              { x: 1, y: -0.2 },
            ],
          },
        ]}
      />,
    );

    expect(screen.getAllByText("primary metric (varies)").length).toBeGreaterThan(0);
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });
});
