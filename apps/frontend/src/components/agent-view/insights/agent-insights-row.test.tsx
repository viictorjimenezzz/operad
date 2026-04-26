import { AgentInsightsRow } from "@/components/agent-view/insights/agent-insights-row";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type React from "react";
import { describe, expect, it, vi } from "vitest";

const agentEventsMock = vi.fn().mockResolvedValue({ run_id: "run-1", events: [] });

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentMeta: vi.fn().mockResolvedValue({
      agent_path: "Root",
      class_name: "Root",
      kind: "leaf",
      hash_content: "hc",
      config: { sampling: {}, resilience: {}, io: {}, runtime: {} },
      rules: [],
      examples: [{ input: { question: "capital of france" }, output: { value: "Paris" } }],
      input_schema: {},
      output_schema: {},
      trainable_paths: [],
      forward_in_overridden: false,
      forward_out_overridden: false,
      forward_in_doc: null,
      forward_out_doc: null,
    }),
    agentEvents: (...args: unknown[]) => agentEventsMock(...args),
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

function renderWithClient(node: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

describe("AgentInsightsRow", () => {
  it("renders contract error for malformed invocations", () => {
    renderWithClient(<AgentInsightsRow summary={summary} invocations={"not-an-object"} />);
    expect(screen.getByText(/invalid invocations contract/i)).toBeTruthy();
  });

  it("shows loading state when invocations are still in flight", () => {
    renderWithClient(<AgentInsightsRow summary={summary} invocations={undefined} />);
    expect(screen.getByText(/loading invocations/i)).toBeTruthy();
  });

  it("shows waiting state when backend reports the run is not ready", () => {
    renderWithClient(
      <AgentInsightsRow
        summary={summary}
        invocations={{ error: "not_found", reason: "root agent path unknown" }}
      />,
    );
    expect(screen.getByText(/waiting for first invocation/i)).toBeTruthy();
  });

  it("renders insights sections for valid payloads", () => {
    agentEventsMock.mockResolvedValue({ run_id: "run-1", events: [] });
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
    expect(screen.queryByText(/^replay$/i)).toBeNull();
    return waitFor(() =>
      expect(screen.getByRole("button", { name: /run example 1/i })).toBeTruthy(),
    );
  });

  it("shows replay panel when chunk events exist", async () => {
    agentEventsMock.mockResolvedValue({
      run_id: "run-1",
      events: [
        {
          type: "agent_event",
          run_id: "run-1",
          agent_path: "Root",
          kind: "chunk",
          input: null,
          output: null,
          started_at: 100.1,
          finished_at: null,
          metadata: { chunk_index: 0, text: "stream" },
          error: null,
        },
      ],
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AgentInsightsRow summary={summary} invocations={invocations} runId="run-1" />
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/^replay$/i)).toBeTruthy();
  });
});
