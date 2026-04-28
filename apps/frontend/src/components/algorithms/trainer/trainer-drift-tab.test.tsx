import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TrainerDriftTab } from "./trainer-drift-tab";

afterEach(cleanup);

describe("TrainerDriftTab", () => {
  it("switches active drift event by clicking epoch buttons", () => {
    render(
      <TrainerDriftTab
        dataDrift={[
          {
            epoch: 0,
            before_text: "old role",
            after_text: "new role",
            selected_path: "role",
            changes: [{ path: "role", before_text: "old role", after_text: "new role" }],
            critique: "tighten",
            gradient_epoch: 0,
            gradient_batch: 1,
            changed_params: ["role"],
            delta_count: 1,
            timestamp: 1,
          },
          {
            epoch: 1,
            before_text: "old task",
            after_text: "new task",
            selected_path: "task",
            changes: [{ path: "task", before_text: "old task", after_text: "new task" }],
            critique: "be specific",
            gradient_epoch: 1,
            gradient_batch: 2,
            changed_params: ["task"],
            delta_count: 1,
            timestamp: 2,
          },
        ]}
      />,
    );

    expect(screen.getByText("drift epoch 1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "epoch 0" }));
    expect(screen.getByText("drift epoch 0")).toBeTruthy();
  });
});
