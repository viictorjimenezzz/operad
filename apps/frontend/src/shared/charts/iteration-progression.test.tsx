import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { IterationProgression } from "./iteration-progression";

afterEach(cleanup);

describe("IterationProgression", () => {
  it("renders empty state when no entries", () => {
    render(<IterationProgression data={{ iterations: [] }} />);
    expect(screen.getByText("no iteration data")).toBeTruthy();
  });

  it("supports phase filter and converged badge", () => {
    render(
      <IterationProgression
        data={{
          threshold: 0.8,
          iterations: [
            { iter_index: 0, phase: "verify", score: 0.4, text: "a", metadata: {} },
            { iter_index: 1, phase: "verify", score: 0.9, text: "b", metadata: {} },
            { iter_index: 2, phase: "reflect", score: 0.2, text: "c", metadata: {} },
          ],
        }}
        phaseFilter="verify"
      />,
    );

    expect(screen.queryByText("reflect")).toBeNull();
    expect(screen.getByText("converged")).toBeTruthy();
  });

  it("renders diff blocks when showDiff is enabled", () => {
    render(
      <IterationProgression
        data={{
          iterations: [
            { iter_index: 0, phase: "reflect", score: 0.2, text: "before", metadata: {} },
            { iter_index: 1, phase: "refine", score: null, text: "after", metadata: {} },
          ],
        }}
        phaseFilter="refine"
        showDiff
      />,
    );

    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("before")).toBeTruthy();
    expect(screen.getAllByText("after").length).toBeGreaterThan(0);
  });
});
