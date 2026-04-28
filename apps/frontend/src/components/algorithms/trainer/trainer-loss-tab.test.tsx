import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TrainerLossTab } from "./trainer-loss-tab";

afterEach(cleanup);

describe("TrainerLossTab", () => {
  it("renders loss plus metric chips and switches overlays", () => {
    render(
      <TrainerLossTab
        dataFitness={[
          {
            gen_index: 0,
            best: 0.8,
            mean: 0.8,
            worst: 0.8,
            train_loss: 0.8,
            val_loss: 0.9,
            lr: 0.1,
            population_scores: [0.8],
            timestamp: 1,
          },
          {
            gen_index: 1,
            best: 0.6,
            mean: 0.6,
            worst: 0.6,
            train_loss: 0.6,
            val_loss: 0.7,
            lr: 0.05,
            population_scores: [0.6],
            timestamp: 2,
          },
        ]}
        dataCheckpoints={[
          {
            epoch: 0,
            train_loss: 0.8,
            val_loss: 0.9,
            score: 0.9,
            metric_snapshot: { accuracy: 0.6, f1: 0.5 },
            is_best: false,
          },
          {
            epoch: 1,
            train_loss: 0.6,
            val_loss: 0.7,
            score: 0.7,
            metric_snapshot: { accuracy: 0.7, f1: 0.65 },
            is_best: true,
          },
        ]}
      />,
    );

    expect(screen.getByRole("button", { name: "loss" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "accuracy" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "f1" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "accuracy" }));
    expect(screen.queryByText("no metric history")).toBeNull();
  });
});
