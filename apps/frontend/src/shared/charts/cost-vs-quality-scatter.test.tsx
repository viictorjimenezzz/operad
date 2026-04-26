import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CostVsQualityScatter } from "./cost-vs-quality-scatter";

afterEach(cleanup);

describe("CostVsQualityScatter", () => {
  it("renders empty state when no points", () => {
    render(<CostVsQualityScatter points={[]} paretoRunIds={[]} />);
    expect(screen.getByText("no cost/quality data")).toBeTruthy();
  });

  it("renders scatter with frontier", () => {
    const { container } = render(
      <CostVsQualityScatter
        points={[
          { runId: "a", label: "A", cost: 10, quality: 0.2 },
          { runId: "b", label: "B", cost: 12, quality: 0.5 },
          { runId: "c", label: "C", cost: 14, quality: 0.4 },
        ]}
        paretoRunIds={["a", "b"]}
      />,
    );

    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
    expect(screen.queryByText("no cost/quality data")).toBeNull();
  });
});
