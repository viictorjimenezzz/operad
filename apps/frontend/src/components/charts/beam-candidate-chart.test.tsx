import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { BeamCandidateChart } from "./beam-candidate-chart";

afterEach(cleanup);

describe("BeamCandidateChart", () => {
  it("renders empty state for missing candidates", () => {
    render(<BeamCandidateChart data={[]} />);
    expect(screen.getByText("no beam candidates")).toBeTruthy();
  });

  it("defaults to the top candidate and updates the selected table from the plot", () => {
    render(
      <MemoryRouter>
        <BeamCandidateChart
          runId="beam-1"
          data={[
            { candidate_index: 0, score: 0.2, text: "c0", timestamp: 1, iter_index: 0 },
            { candidate_index: 1, score: 0.8, text: "c1", timestamp: 1, iter_index: 0 },
            { candidate_index: 2, score: 0.9, text: "c2", timestamp: 1, iter_index: 0 },
          ]}
          iterationsData={{
            iterations: [
              {
                iter_index: 0,
                phase: "prune",
                metadata: { top_indices: [2, 1], dropped_indices: [0] },
              },
            ],
          }}
          dataEvents={[
            agentEnd("Reasoner", 0, "prompt 0", "c0"),
            agentEnd("Reasoner", 1, "prompt 1", "c1"),
            agentEnd("Reasoner", 2, "prompt 2", "c2"),
            criticEnd(0, "c0", 0.2, "weak"),
            criticEnd(1, "c1", 0.8, "good"),
            criticEnd(2, "c2", 0.9, "best"),
          ]}
          dataAgentsSummary={{
            run_id: "beam-1",
            agents: [{ agent_path: "Critic", langfuse_url: "https://langfuse.test/trace/beam-1" }],
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Candidate scores")).toBeTruthy();
    expect(screen.getByRole("img", { name: "score histogram" })).toBeTruthy();
    expect(screen.getByText("c2")).toBeTruthy();
    expect(screen.getByText("prompt 2")).toBeTruthy();
    expect(screen.getByText("best")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "select candidate 0" }));
    expect(screen.getByText("c0")).toBeTruthy();
    expect(screen.getByText("prompt 0")).toBeTruthy();
    expect(screen.getByText("weak")).toBeTruthy();
  });
});

function agentEnd(agentPath: string, index: number, prompt: string, answer: string) {
  return {
    type: "agent_event",
    run_id: "beam-1",
    agent_path: agentPath,
    kind: "end",
    input: { goal: `candidate ${index}` },
    output: {
      response: { answer },
      latency_ms: 100 + index,
      hash_prompt: `prompt-${index}`,
    },
    started_at: index,
    finished_at: index + 0.1,
    metadata: {
      invoke_id: `${agentPath}-${index}`,
      class_name: agentPath,
      hash_content: `${agentPath}-hash`,
      prompt_user: prompt,
    },
  };
}

function criticEnd(index: number, answer: string, score: number, rationale: string) {
  return {
    type: "agent_event",
    run_id: "beam-1",
    agent_path: "Critic",
    kind: "end",
    input: { input: { goal: "pick rollout" }, output: { answer } },
    output: {
      response: { score, rationale },
      latency_ms: 50 + index,
      hash_prompt: `critic-${index}`,
    },
    started_at: 10 + index,
    finished_at: 10 + index + 0.1,
    metadata: {
      invoke_id: `critic-${index}`,
      class_name: "Critic",
      hash_content: "critic-hash",
    },
  };
}
