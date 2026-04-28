import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AutoResearcherAttemptsTab } from "./attempts-tab";

afterEach(cleanup);

const iterationsPayload = {
  iterations: [
    {
      iter_index: 0,
      phase: "reason",
      score: 0.63,
      text: "Initial reasoning for attempt 1",
      metadata: { attempt_index: 0 },
    },
    {
      iter_index: 1,
      phase: "reflect",
      score: 0.63,
      text: "Reflection notes for attempt 1",
      metadata: { attempt_index: 0 },
    },
    {
      iter_index: 0,
      phase: "reason",
      score: 0.88,
      text: "Best reasoning for attempt 2",
      metadata: { attempt_index: 1 },
    },
  ],
  max_iter: 2,
  threshold: 0.8,
  converged: null,
};

describe("<AutoResearcherAttemptsTab />", () => {
  it("renders attempts x phase swimlane and opens a side drawer", () => {
    render(<AutoResearcherAttemptsTab dataIterations={iterationsPayload} />);

    expect(screen.getByText("Attempt #1")).toBeDefined();
    expect(screen.getByText("Attempt #2")).toBeDefined();
    expect(screen.getByText("plan")).toBeDefined();
    expect(screen.getByText("reason")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Attempt #2 reason" }));

    expect(screen.getByRole("dialog", { name: "Attempt phase output" })).toBeDefined();
    expect(screen.getAllByText("Best reasoning for attempt 2").length).toBeGreaterThan(0);
  });

  it("shows an empty state with no iterations", () => {
    render(
      <AutoResearcherAttemptsTab
        dataIterations={{ iterations: [], max_iter: null, threshold: null, converged: null }}
      />,
    );

    expect(screen.getByText("no attempt iterations")).toBeDefined();
  });
});
