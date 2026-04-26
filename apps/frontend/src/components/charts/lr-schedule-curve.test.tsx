import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);
import { LrScheduleCurve } from "./lr-schedule-curve";

describe("LrScheduleCurve", () => {
  it("renders empty state when no rows", () => {
    render(<LrScheduleCurve data={[]} />);
    expect(screen.getByText("no LR schedule data")).toBeTruthy();
  });

  it("renders chart when lr points exist", () => {
    render(
      <LrScheduleCurve
        data={[
          {
            gen_index: 0,
            best: 0.9,
            mean: 0.9,
            worst: 0.9,
            train_loss: 0.9,
            val_loss: null,
            lr: 0.1,
            population_scores: [0.9],
            timestamp: 0,
          },
        ]}
      />,
    );
    expect(screen.queryByText("no LR schedule data")).toBeNull();
  });
});
