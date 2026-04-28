import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AutoResearcherPlanTab } from "./plan-tab";

afterEach(cleanup);

describe("<AutoResearcherPlanTab />", () => {
  it("renders planner steps from the first plan-like event", () => {
    render(
      <AutoResearcherPlanTab
        dataEvents={{
          events: [
            {
              type: "algo_event",
              kind: "iteration",
              payload: {
                phase: "plan",
                plan: {
                  steps: [
                    { text: "Define search scope", status: "done" },
                    { text: "Collect sources", status: "in-progress" },
                    { text: "Synthesize answer", status: "planned" },
                  ],
                },
              },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Research plan")).toBeDefined();
    expect(screen.getByText("Define search scope")).toBeDefined();
    expect(screen.getByText("Collect sources")).toBeDefined();
    expect(screen.getByText("Synthesize answer")).toBeDefined();
  });

  it("shows an empty state when no plan event exists", () => {
    render(<AutoResearcherPlanTab dataEvents={{ events: [] }} />);

    expect(screen.getByText("plan steps unavailable")).toBeDefined();
  });
});
