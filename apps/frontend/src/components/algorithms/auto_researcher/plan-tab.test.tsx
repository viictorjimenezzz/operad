import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AutoResearcherPlanTab } from "./plan-tab";

afterEach(cleanup);

const summary = {
  run_id: "auto-run",
  started_at: 100,
  last_event_at: 110,
  state: "ended",
  has_graph: false,
  is_algorithm: true,
  algorithm_path: "AutoResearcher",
  algorithm_kinds: ["plan", "iteration"],
  root_agent_path: null,
  event_counts: {},
  event_total: 9,
  duration_ms: 1234,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 0,
  completion_tokens: 0,
  error: null,
  algorithm_terminal_score: 0.9,
  synthetic: false,
  parent_run_id: null,
  algorithm_class: "AutoResearcher",
};

const iterations = {
  iterations: [
    { iter_index: 0, phase: "reason", score: 0.8, text: null, metadata: { attempt_index: 0 } },
    { iter_index: 0, phase: "reason", score: 0.9, text: null, metadata: { attempt_index: 1 } },
  ],
  max_iter: 1,
  threshold: 0.8,
  converged: null,
};

const attachedRunEvents = {
  run_id: "auto-run",
  events: [
    {
      type: "algo_event",
      kind: "plan",
      payload: { attempt_index: 0, plan: { query: "verify plan tab" } },
    },
    {
      type: "agent_event",
      agent_path: "Retriever",
      kind: "end",
      output: {
        response: {
          items: [
            { source: "dashboard-readme", text: "Plan tab shows algorithm data.", score: 0.94 },
          ],
        },
      },
    },
    {
      type: "algo_event",
      kind: "plan",
      payload: { attempt_index: 1, plan: { query: "verify best tab" } },
    },
    {
      type: "agent_event",
      agent_path: "Retriever",
      kind: "end",
      output: {
        response: {
          items: [
            { source: "examples-readme", text: "Best tab shows selected answer.", score: 0.82 },
          ],
        },
      },
    },
  ],
};

describe("<AutoResearcherPlanTab />", () => {
  it("renders attached-run plan events, retrieved evidence, and moved run details", () => {
    render(
      <AutoResearcherPlanTab
        dataSummary={summary}
        dataIterations={iterations}
        dataEvents={attachedRunEvents}
        dataLangfuseUrl="http://localhost:7000/trace/auto-run"
      />,
    );

    expect(screen.getByText("Attempt #1 plan")).toBeDefined();
    expect(screen.getByText("Attempt #2 plan")).toBeDefined();
    expect(screen.getByText(/dashboard-readme/)).toBeDefined();
    expect(screen.getByText(/examples-readme/)).toBeDefined();
    expect(screen.getByText("attempts")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("best")).toBeDefined();
    expect(screen.getByText("0.900")).toBeDefined();
    expect(screen.getByText("langfuse")).toBeDefined();
  });

  it("shows an empty state when no plan event exists", () => {
    render(<AutoResearcherPlanTab dataSummary={summary} dataEvents={{ events: [] }} />);

    expect(screen.getByText("plans not available")).toBeDefined();
  });
});
