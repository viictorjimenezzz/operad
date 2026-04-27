import { TabExperiment } from "@/components/agent-view/graph/inspector/tab-experiment";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type React from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/hooks/use-runs", () => ({
  useManifest: () => ({ data: { allowExperiment: false }, isLoading: false }),
  useAgentMeta: () => ({
    data: {
      role: "Role",
      task: "Task",
      rules: [],
    },
  }),
}));

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentInvocations: vi.fn(async () => ({ agent_path: "Root.leaf", invocations: [] })),
    agentInvoke: vi.fn(),
  },
}));

function wrapper(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("TabExperiment", () => {
  it("shows a disabled capability state when experiments are not allowed", () => {
    render(wrapper(<TabExperiment runId="run-1" agentPath="Root.leaf" />));

    expect(screen.getByText("Edit & run is disabled")).toBeTruthy();
    expect(screen.queryByText("run")).toBeNull();
  });
});
