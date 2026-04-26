import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { ConvergenceCurve } from "./convergence-curve";

afterEach(cleanup);

describe("ConvergenceCurve", () => {
  it("renders empty state when data is missing", () => {
    render(<ConvergenceCurve data={undefined} />);
    expect(screen.getByText("no iteration data")).toBeTruthy();
  });

  it("renders a chart when iterations are present", () => {
    render(
      <ConvergenceCurve
        data={{
          threshold: 0.8,
          converged: true,
          iterations: [
            { iter_index: 0, score: 0.4 },
            { iter_index: 1, score: null },
            { iter_index: 2, score: 0.91 },
          ],
        }}
      />,
    );
    expect(screen.queryByText("no iteration data")).toBeNull();
    expect(document.querySelector(".recharts-responsive-container")).toBeTruthy();
  });
});
