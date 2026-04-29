import { BeamMetricsTab } from "@/components/algorithms/beam/metrics-tab";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("BeamMetricsTab", () => {
  it("renders candidate score and invocation metric charts", () => {
    render(
      <BeamMetricsTab
        data={[
          { candidate_index: 0, score: 0.4, text: "c0", timestamp: 1, iter_index: 0 },
          { candidate_index: 1, score: 0.9, text: "c1", timestamp: 1, iter_index: 0 },
        ]}
        dataEvents={[
          agentEnd("Reasoner", 0, "c0", 100, 10, 4, 0.01),
          agentEnd("Reasoner", 1, "c1", 120, 12, 5, 0.02),
          criticEnd(0, "c0", 40, 6, 2, 0.005),
          criticEnd(1, "c1", 60, 7, 3, 0.006),
        ]}
      />,
    );

    expect(screen.getAllByText("score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("generator latency").length).toBeGreaterThan(0);
    expect(screen.getAllByText("critic latency").length).toBeGreaterThan(0);
    expect(screen.getAllByText("total latency").length).toBeGreaterThan(0);
    expect(screen.getAllByText("cost").length).toBeGreaterThan(0);
    expect(screen.getAllByText("prompt tokens").length).toBeGreaterThan(0);
    expect(screen.getAllByText("completion tokens").length).toBeGreaterThan(0);
  });

  it("renders an empty state when no numeric metrics are available", () => {
    render(
      <BeamMetricsTab
        data={[{ candidate_index: 0, score: null, text: "c0", timestamp: 1, iter_index: 0 }]}
      />,
    );

    expect(screen.getByText("no beam metrics")).toBeTruthy();
  });
});

function agentEnd(
  agentPath: string,
  index: number,
  answer: string,
  latencyMs: number,
  promptTokens: number,
  completionTokens: number,
  costUsd: number,
) {
  return {
    type: "agent_event",
    run_id: "beam-1",
    agent_path: agentPath,
    kind: "end",
    input: { goal: `candidate ${index}` },
    output: {
      response: { answer },
      latency_ms: latencyMs,
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      cost_usd: costUsd,
    },
    started_at: index,
    finished_at: index + 0.1,
    metadata: { invoke_id: `${agentPath}-${index}`, class_name: agentPath },
  };
}

function criticEnd(
  index: number,
  answer: string,
  latencyMs: number,
  promptTokens: number,
  completionTokens: number,
  costUsd: number,
) {
  return {
    type: "agent_event",
    run_id: "beam-1",
    agent_path: "Critic",
    kind: "end",
    input: { input: { goal: "pick rollout" }, output: { answer } },
    output: {
      response: { score: index, rationale: "ok" },
      latency_ms: latencyMs,
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      cost_usd: costUsd,
    },
    started_at: 10 + index,
    finished_at: 10 + index + 0.1,
    metadata: { invoke_id: `critic-${index}`, class_name: "Critic" },
  };
}
