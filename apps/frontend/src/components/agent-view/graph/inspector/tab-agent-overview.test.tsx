import { TabAgentOverview } from "@/components/agent-view/graph/inspector/tab-agent-overview";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentMeta = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/use-runs", () => ({
  useAgentMeta: mockUseAgentMeta,
}));

const fixtureMeta = {
  agent_path: "Root.researcher",
  class_name: "Reasoner",
  kind: "leaf",
  hash_content: "abc123def456789",
  role: "You are a research analyst.",
  task: "Summarize findings.",
  rules: ["Be concise", "Cite sources"],
  examples: [
    {
      input: { query: "test" },
      output: { result: "ok" },
    },
  ],
  config: { backend: "openai" },
  input_schema: {
    key: "tests.Input",
    name: "Input",
    fields: [
      {
        name: "query",
        type: "str",
        description: "Search query.",
        system: false,
        has_default: false,
        default: null,
      },
      {
        name: "policy",
        type: "str",
        description: "Routing policy.",
        system: true,
        has_default: true,
        default: "web",
      },
    ],
  },
  output_schema: {
    key: "tests.Output",
    name: "Output",
    fields: [
      {
        name: "result",
        type: "str",
        description: "Final answer.",
        system: false,
        has_default: false,
        default: null,
      },
    ],
  },
  forward_in_overridden: false,
  forward_out_overridden: true,
  trainable_paths: ["role"],
  langfuse_search_url: null,
};

function wrapper(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  cleanup();
});

describe("TabAgentOverview", () => {
  beforeEach(() => {
    mockUseAgentMeta.mockReturnValue({ isLoading: false, error: null, data: fixtureMeta });
  });

  it("renders input and output schema summaries", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText("tests.Input")).toBeTruthy();
    expect(screen.getByText("tests.Output")).toBeTruthy();
    expect(screen.getByText("query")).toBeTruthy();
    expect(screen.getByText("result")).toBeTruthy();
  });

  it("renders field system markers, descriptions, and defaults", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText("system")).toBeTruthy();
    expect(screen.getByText("Routing policy.")).toBeTruthy();
    expect(screen.getByText('default "web"')).toBeTruthy();
  });

  it("does not render instance-definition sections", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.queryByText("identity")).toBeNull();
    expect(screen.queryByText("role")).toBeNull();
    expect(screen.queryByText("task")).toBeNull();
    expect(screen.queryByText(/rules/i)).toBeNull();
    expect(screen.queryByText("config")).toBeNull();
    expect(screen.queryByText("hooks")).toBeNull();
  });

  it("shows loading state when isLoading is true", () => {
    mockUseAgentMeta.mockReturnValue({ isLoading: true, error: null, data: undefined });
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText(/loading/i)).toBeTruthy();
  });
});
