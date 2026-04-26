import { PromptDiffView } from "@/components/agent-view/drawer/views/prompts/prompt-diff";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentPrompts: vi.fn(),
    agentInvocations: vi.fn(),
    agentMeta: vi.fn(),
    agentEvents: vi.fn(),
  },
}));

import { dashboardApi } from "@/lib/api/dashboard";

function wrap(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("PromptDiffView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    Object.defineProperty(window, "open", {
      configurable: true,
      value: vi.fn(),
    });

    vi.mocked(dashboardApi.agentPrompts).mockResolvedValue({
      agent_path: "Root",
      renderer: "xml",
      entries: [
        {
          invocation_id: "Root:0",
          started_at: 1,
          hash_prompt: "h1",
          system: "<role>a</role>",
          user: "u1",
          replayed: true,
        },
        {
          invocation_id: "Root:1",
          started_at: 2,
          hash_prompt: "h2",
          system: "<role>b</role>",
          user: "u2",
          replayed: true,
        },
        {
          invocation_id: "Root:2",
          started_at: 3,
          hash_prompt: "h3",
          system: "<role>c</role>",
          user: "u3",
          replayed: true,
        },
      ],
    });

    vi.mocked(dashboardApi.agentInvocations).mockResolvedValue({
      agent_path: "Root",
      invocations: [
        {
          id: "Root:0",
          started_at: 1,
          finished_at: 2,
          latency_ms: 100,
          prompt_tokens: 1,
          completion_tokens: 1,
          hash_prompt: "h1",
          hash_input: "i1",
          hash_content: "c1",
          status: "ok",
          error: null,
          langfuse_url: null,
          script: null,
        },
        {
          id: "Root:1",
          started_at: 2,
          finished_at: 3,
          latency_ms: 100,
          prompt_tokens: 1,
          completion_tokens: 1,
          hash_prompt: "h2",
          hash_input: "i2",
          hash_content: "c2",
          status: "ok",
          error: null,
          langfuse_url: "http://lf.example/trace/run-1",
          script: null,
        },
        {
          id: "Root:2",
          started_at: 3,
          finished_at: 4,
          latency_ms: 100,
          prompt_tokens: 1,
          completion_tokens: 1,
          hash_prompt: "h3",
          hash_input: "i3",
          hash_content: "c3",
          status: "ok",
          error: null,
          langfuse_url: "http://lf.example/trace/run-1b",
          script: null,
        },
      ],
    });

    vi.mocked(dashboardApi.agentMeta).mockResolvedValue({
      agent_path: "Root",
      class_name: "Root",
      kind: "leaf",
      hash_content: "hc",
      role: null,
      task: null,
      rules: [],
      examples: [],
      config: { backend: null, model: null, sampling: {}, resilience: {}, io: {}, runtime: {} },
      input_schema: {},
      output_schema: {},
      forward_in_overridden: false,
      forward_out_overridden: false,
      trainable_paths: [],
      langfuse_search_url: "http://lf.example/traces?search=Root",
    });

    vi.mocked(dashboardApi.agentEvents).mockResolvedValue({
      run_id: "run-1",
      events: [
        {
          type: "agent_event",
          run_id: "run-1",
          agent_path: "Root",
          kind: "start",
          input: { q: "one" },
          output: null,
          started_at: 1,
          finished_at: null,
          metadata: {},
          error: null,
        },
        {
          type: "agent_event",
          run_id: "run-1",
          agent_path: "Root",
          kind: "start",
          input: { q: "two" },
          output: null,
          started_at: 2,
          finished_at: null,
          metadata: {},
          error: null,
        },
        {
          type: "agent_event",
          run_id: "run-1",
          agent_path: "Root",
          kind: "start",
          input: { q: "three" },
          output: null,
          started_at: 3,
          finished_at: null,
          metadata: {},
          error: null,
        },
      ],
    });
  });

  it("focuses transition and supports toolbar actions", async () => {
    wrap(<PromptDiffView runId="run-1" agentPath="Root" focus="Root:2" />);

    await waitFor(() => expect(screen.getByText(/comparing Root:1 → Root:2/i)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /copy as markdown/i }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });

    const openButtons = screen.getAllByRole("button", { name: /open in langfuse/i });
    fireEvent.click(openButtons[openButtons.length - 1] as Element);
    expect(window.open).toHaveBeenCalledWith(
      "http://lf.example/trace/run-1b",
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("falls back to search url for langfuse action", async () => {
    vi.mocked(dashboardApi.agentInvocations).mockResolvedValueOnce({
      agent_path: "Root",
      invocations: [],
    });

    wrap(<PromptDiffView runId="run-1" agentPath="Root" focus={null} />);
    await waitFor(() => expect(screen.getByText(/comparing Root:0 → Root:1/i)).toBeTruthy());

    const openButtons = screen.getAllByRole("button", { name: /open in langfuse/i });
    fireEvent.click(openButtons[openButtons.length - 1] as Element);
    expect(window.open).toHaveBeenCalledWith(
      "http://lf.example/traces?search=Root",
      "_blank",
      "noopener,noreferrer",
    );
  });
});
