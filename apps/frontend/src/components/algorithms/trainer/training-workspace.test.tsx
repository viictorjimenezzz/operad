import { TrainingWorkspace } from "@/components/algorithms/trainer/training-workspace";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("TrainingWorkspace", () => {
  it("renders the six headline panels with view-full affordances", () => {
    render(
      <MemoryRouter>
        <TrainingWorkspace
          dataFitness={[
            {
              gen_index: 0,
              best: 0.8,
              mean: 0.8,
              worst: 0.8,
              train_loss: 0.8,
              val_loss: 0.9,
              lr: 1,
              population_scores: [0.8],
              timestamp: 1,
            },
            {
              gen_index: 1,
              best: 0.5,
              mean: 0.5,
              worst: 0.5,
              train_loss: 0.5,
              val_loss: 0.6,
              lr: 0.5,
              population_scores: [0.5],
              timestamp: 2,
            },
          ]}
          dataCheckpoints={[
            {
              epoch: 1,
              train_loss: 0.5,
              val_loss: 0.6,
              score: 0.6,
              lr: 0.5,
              parameter_snapshot: { task: "'better task'" },
              is_best: true,
            },
          ]}
          dataGradients={[
            {
              epoch: 1,
              batch: 2,
              message: "tighten answer",
              severity: 0.8,
              target_paths: ["task"],
              by_field: { task: "be specific" },
              applied_diff: "task\n- old\n+ new",
              timestamp: 2,
            },
          ]}
          dataDrift={[
            {
              epoch: 1,
              before_text: "old",
              after_text: "new",
              selected_path: "task",
              changes: [{ path: "task", before_text: "old", after_text: "new" }],
              critique: "tighten",
              gradient_epoch: 1,
              gradient_batch: 2,
              changed_params: ["task"],
              delta_count: 1,
              timestamp: 2,
            },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Loss curve")).toBeTruthy();
    expect(screen.getByText("LR schedule")).toBeTruthy();
    expect(screen.getByText("Gradient log")).toBeTruthy();
    expect(screen.getByText("Checkpoint timeline")).toBeTruthy();
    expect(screen.getByText("PromptDrift timeline")).toBeTruthy();
    expect(screen.getByText("Parameter evolution")).toBeTruthy();
    expect(screen.getAllByText("View full")).toHaveLength(6);
  });
});
