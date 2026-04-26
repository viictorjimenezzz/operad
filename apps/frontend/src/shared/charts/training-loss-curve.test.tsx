import { afterEach, describe, expect, it } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

afterEach(cleanup);
import { TrainingLossCurve } from "./training-loss-curve";

describe("TrainingLossCurve", () => {
  it("renders empty state when no rows", () => {
    render(<TrainingLossCurve data={[]} checkpointData={[]} />);
    expect(screen.getByText("no loss data yet")).toBeTruthy();
  });

  it("renders chart with val/lr/checkpoint", () => {
    render(
      <TrainingLossCurve
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
            timestamp: 1,
          },
          {
            gen_index: 1,
            best: 0.7,
            mean: 0.7,
            worst: 0.7,
            train_loss: 0.7,
            val_loss: null,
            lr: 0.05,
            population_scores: [0.7],
            timestamp: 2,
          },
        ]}
        checkpointData={[
          {
            epoch: 0,
            train_loss: 0.9,
            val_loss: 1.0,
            score: 1.0,
            lr: 0.1,
            metric_snapshot: { train_loss: 0.9, val_loss: 1.0, score: 1.0 },
            parameter_snapshot: { role: "r0" },
            is_best: false,
          },
          {
            epoch: 1,
            train_loss: 0.7,
            val_loss: 0.8,
            score: 0.8,
            lr: 0.05,
            metric_snapshot: { train_loss: 0.7, val_loss: 0.8, score: 0.8 },
            parameter_snapshot: { role: "r1" },
            is_best: true,
          },
        ]}
      />,
    );
    expect(screen.queryByText("no loss data yet")).toBeNull();
  });
});
