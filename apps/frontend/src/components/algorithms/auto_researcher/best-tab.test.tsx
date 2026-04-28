import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AutoResearcherBestTab } from "./best-tab";

afterEach(cleanup);

describe("<AutoResearcherBestTab />", () => {
  it("shows the winning attempt reasoning and answer from agent events", () => {
    render(
      <AutoResearcherBestTab
        dataSummary={{ algorithm_terminal_score: 0.88 }}
        dataIterations={{
          iterations: [
            {
              iter_index: 0,
              phase: "reason",
              score: 0.61,
              text: null,
              metadata: { attempt_index: 0 },
            },
            {
              iter_index: 0,
              phase: "reason",
              score: 0.88,
              text: null,
              metadata: { attempt_index: 1 },
            },
          ],
          max_iter: 1,
          threshold: 0.8,
          converged: null,
        }}
        dataEvents={{
          events: [
            {
              type: "algo_event",
              kind: "plan",
              payload: { attempt_index: 0, plan: { query: "first attempt" } },
            },
            {
              type: "algo_event",
              kind: "plan",
              payload: { attempt_index: 1, plan: { query: "second attempt" } },
            },
            {
              type: "agent_event",
              agent_path: "Reasoner",
              kind: "end",
              output: {
                response: {
                  reasoning: "Reasoning trace for first attempt",
                  answer: "First answer",
                },
              },
            },
            {
              type: "agent_event",
              agent_path: "Reasoner",
              kind: "end",
              output: {
                response: {
                  reasoning: "Reasoning trace for winner",
                  answer: "Final winning answer",
                },
              },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Best attempt")).toBeDefined();
    expect(screen.getByText("Reasoning trace for winner")).toBeDefined();
    expect(screen.getByText("Final winning answer")).toBeDefined();
    expect(screen.getAllByText("0.88").length).toBeGreaterThan(0);
  });

  it("shows empty states when winner payload text is missing", () => {
    render(
      <AutoResearcherBestTab
        dataSummary={{ algorithm_terminal_score: null }}
        dataIterations={{ iterations: [], max_iter: null, threshold: null, converged: null }}
        dataEvents={{ events: [] }}
      />,
    );

    expect(screen.getByText("reasoning not emitted")).toBeDefined();
    expect(screen.getByText("answer not emitted")).toBeDefined();
  });
});
