import { AgentInsightsRow } from "@/components/agent-view/insights/agent-insights-row";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentMeta: vi.fn().mockResolvedValue({
      agent_path: "Root",
      class_name: "Root",
      kind: "leaf",
      hash_content: "hc",
      config: { sampling: {}, resilience: {}, io: {}, runtime: {} },
      rules: [],
      examples: [],
      input_schema: {},
      output_schema: {},
      trainable_paths: [],
      forward_in_overridden: false,
      forward_out_overridden: false,
    }),
  },
}));

const summary = {
  run_id: "run-1",
  started_at: 100,
  last_event_at: 101,
  state: "running",
  has_graph: true,
  is_algorithm: false,
  algorithm_path: null,
  algorithm_kinds: [],
  root_agent_path: "Root",
  script: null,
  event_counts: {},
  event_total: 2,
  duration_ms: 1000,
  generations: [],
  iterations: [],
  rounds: [],
  candidates: [],
  batches: [],
  prompt_tokens: 0,
  completion_tokens: 0,
  error: null,
  algorithm_terminal_score: null,
  synthetic: false,
  parent_run_id: null,
  algorithm_class: null,
};

const invocations = {
  agent_path: "Root",
  invocations: [
    {
      id: "i1",
      started_at: 100,
      hash_prompt: "p1",
      hash_input: "i1",
      hash_content: "c1",
      status: "ok",
      input: { question: "q1" },
    },
    {
      id: "i2",
      started_at: 101,
      hash_prompt: "p2",
      hash_input: "i1",
      hash_content: "c1",
      status: "ok",
      input: { question: "q2" },
    },
  ],
};

describe("AgentInsightsRow", () => {
  it("renders contract error for malformed invocations", () => {
    render(<AgentInsightsRow summary={summary} invocations={{ broken: true }} />);
    expect(screen.getByText(/invalid invocations contract/i)).toBeTruthy();
  });

  it("renders insights sections for valid payloads", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AgentInsightsRow summary={summary} invocations={invocations} runId="run-1" />
      </QueryClientProvider>,
    );
    expect(screen.getByText(/fingerprint/i)).toBeTruthy();
    expect(screen.getByText(/prompt drift/i)).toBeTruthy();
    expect(screen.getByText(/cost \/ latency \/ tokens/i)).toBeTruthy();
  });
});
