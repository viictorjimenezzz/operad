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
      text: null,
      metadata: { attempt_index: 0 },
    },
    {
      iter_index: 1,
      phase: "reflect",
      score: 0.63,
      text: null,
      metadata: { attempt_index: 0 },
    },
  ],
  max_iter: 2,
  threshold: 0.8,
  converged: null,
};

const eventsPayload = {
  run_id: "auto-run",
  events: [
    {
      type: "algo_event",
      kind: "plan",
      payload: { attempt_index: 0, plan: { query: "dashboard algorithm view" } },
    },
    {
      type: "agent_event",
      agent_path: "Retriever",
      kind: "end",
      output: { response: { items: [{ source: "dashboard-readme", text: "Inspect tabs." }] } },
    },
    {
      type: "agent_event",
      agent_path: "Reasoner",
      kind: "end",
      output: {
        response: {
          reasoning: "Initial reasoning for attempt 1",
          answer: "Inspect the Plan and Best tabs.",
        },
      },
    },
    {
      type: "agent_event",
      agent_path: "Critic",
      kind: "end",
      output: { response: { score: 0.63, rationale: "Needs the attempts tab." } },
    },
    {
      type: "agent_event",
      agent_path: "Reflector",
      kind: "end",
      output: {
        response: {
          deficiencies: ["Attempts tab missing."],
          needs_revision: true,
          suggested_revision: "Include attempts.",
        },
      },
    },
  ],
};

describe("<AutoResearcherAttemptsTab />", () => {
  it("renders plan, retrieve, reason, critique, and reflect cells from events", () => {
    render(
      <AutoResearcherAttemptsTab dataIterations={iterationsPayload} dataEvents={eventsPayload} />,
    );

    expect(screen.getByText("Attempt #1")).toBeDefined();
    expect(screen.getByText("plan")).toBeDefined();
    expect(screen.getByText("retrieve")).toBeDefined();
    expect(screen.getByText("critique")).toBeDefined();
    expect(screen.getByText(/dashboard algorithm view/)).toBeDefined();
    expect(screen.getByText(/Initial reasoning for attempt 1/)).toBeDefined();
    expect(screen.getByText(/Needs the attempts tab/)).toBeDefined();
    expect(screen.getByText(/Attempts tab missing/)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Attempt #1 retrieve" }));

    expect(screen.getByRole("dialog", { name: "Attempt phase output" })).toBeDefined();
    expect(screen.getAllByText(/dashboard-readme/).length).toBeGreaterThan(0);
  });

  it("shows an empty state with no iterations or events", () => {
    render(
      <AutoResearcherAttemptsTab
        dataIterations={{ iterations: [], max_iter: null, threshold: null, converged: null }}
        dataEvents={{ events: [] }}
      />,
    );

    expect(screen.getByText("no attempt iterations")).toBeDefined();
  });
});
