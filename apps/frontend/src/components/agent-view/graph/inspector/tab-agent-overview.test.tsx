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
  input_schema: { query: "string" },
  output_schema: { result: "string" },
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

  it("renders identity section with class, kind, and agent path", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText("identity")).toBeTruthy();
    expect(screen.getByText("Reasoner")).toBeTruthy();
    expect(screen.getByText("leaf")).toBeTruthy();
    expect(screen.getByText("Root.researcher")).toBeTruthy();
  });

  it("renders role and task section labels", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    const allRole = screen.getAllByText("role");
    expect(allRole.length).toBeGreaterThan(0);
    const allTask = screen.getAllByText("task");
    expect(allTask.length).toBeGreaterThan(0);
  });

  it("renders rules as a numbered list", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText(/rules \(2\)/i)).toBeTruthy();
    expect(screen.getByText("Be concise")).toBeTruthy();
    expect(screen.getByText("Cite sources")).toBeTruthy();
  });

  it("renders examples section", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText(/examples \(1\)/i)).toBeTruthy();
  });

  it("renders config section", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText("config")).toBeTruthy();
  });

  it("renders hooks section with overridden state", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText("hooks")).toBeTruthy();
    expect(screen.getByText(/forward_out overridden/)).toBeTruthy();
    expect(screen.getByText(/forward_in default/)).toBeTruthy();
  });

  it("renders input and output section labels", () => {
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    const allInput = screen.getAllByText("input");
    expect(allInput.length).toBeGreaterThan(0);
    const allOutput = screen.getAllByText("output");
    expect(allOutput.length).toBeGreaterThan(0);
  });

  it("shows loading state when isLoading is true", () => {
    mockUseAgentMeta.mockReturnValue({ isLoading: true, error: null, data: undefined });
    render(wrapper(<TabAgentOverview runId="run-1" agentPath="Root.researcher" />));
    expect(screen.getByText(/loading/i)).toBeTruthy();
  });
});
