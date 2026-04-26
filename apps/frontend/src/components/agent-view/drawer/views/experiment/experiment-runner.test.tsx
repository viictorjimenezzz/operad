import { ExperimentRunner } from "@/components/agent-view/drawer/views/experiment/experiment-runner";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentMeta: vi.fn(),
    agentInvocations: vi.fn(),
    agentInvoke: vi.fn(),
  },
  HttpError: class HttpError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

import { dashboardApi } from "@/lib/api/dashboard";

function wrap(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ExperimentRunner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardApi.agentMeta).mockResolvedValue({
      agent_path: "Root",
      class_name: "Root",
      kind: "leaf",
      hash_content: "hc",
      role: "role",
      task: "task",
      rules: ["r1"],
      examples: [{ input: { q: "a" }, output: { value: 1 } }],
      config: {
        backend: null,
        model: null,
        sampling: { temperature: 0.2 },
        resilience: {},
        io: {},
        runtime: {},
      },
      input_schema: {},
      output_schema: {},
      forward_in_overridden: false,
      forward_out_overridden: false,
      forward_in_doc: null,
      forward_out_doc: null,
      trainable_paths: [],
      langfuse_search_url: null,
    });
    vi.mocked(dashboardApi.agentInvocations).mockResolvedValue({
      agent_path: "Root",
      invocations: [
        {
          id: "Root:0",
          started_at: 1,
          finished_at: 2,
          latency_ms: 1,
          prompt_tokens: 1,
          completion_tokens: 1,
          hash_prompt: "p1",
          hash_input: "h1",
          hash_content: "c1",
          status: "ok",
          error: null,
          langfuse_url: null,
          script: null,
          input: { q: "historic" },
        },
      ],
    });
    vi.mocked(dashboardApi.agentInvoke).mockResolvedValue({
      response: { value: 2 },
      hash_prompt: "hp",
      hash_input: "hi",
      latency_ms: 12,
      prompt_tokens: 11,
      completion_tokens: 9,
      metadata: {
        experiment: true,
        hash_content: "hc2",
        agent_path: "Root",
        run_id: "run-1",
      },
    });
  });

  it("runs a single experiment invoke", async () => {
    wrap(<ExperimentRunner runId="run-1" agentPath="Root" />);

    await waitFor(() => expect(screen.getByText(/input picker/i)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    await waitFor(() => expect(dashboardApi.agentInvoke).toHaveBeenCalledTimes(1));
    expect(vi.mocked(dashboardApi.agentInvoke).mock.calls[0]?.[2]).toMatchObject({
      input: { q: "historic" },
    });
    expect(screen.getByText(/experiment/i)).toBeTruthy();
  });

  it("runs compare mode with two invokes", async () => {
    wrap(<ExperimentRunner runId="run-1" agentPath="Root" />);

    await waitFor(() => expect(screen.getByText(/compare with live baseline/i)).toBeTruthy());
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));

    await waitFor(() => expect(dashboardApi.agentInvoke).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText(/live baseline/i).length).toBeGreaterThan(0);
  });
});
