import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TrainerScheduleTab } from "./trainer-schedule-tab";

afterEach(cleanup);

describe("TrainerScheduleTab", () => {
  it("marks the best epoch with a star", () => {
    render(
      <TrainerScheduleTab
        dataFitness={[
          {
            gen_index: 0,
            best: 0.9,
            mean: 0.9,
            worst: 0.9,
            train_loss: 0.9,
            val_loss: 1.0,
            lr: 0.1,
            population_scores: [0.9],
            timestamp: 1,
          },
        ]}
        dataCheckpoints={[
          {
            epoch: 0,
            train_loss: 0.9,
            val_loss: 1.0,
            score: 1.0,
            is_best: false,
          },
          {
            epoch: 1,
            train_loss: 0.7,
            val_loss: 0.8,
            score: 0.8,
            is_best: true,
          },
        ]}
      />,
    );

    expect(screen.getByText("best epoch 1")).toBeTruthy();
    expect(screen.getByText("★")).toBeTruthy();
  });
});
