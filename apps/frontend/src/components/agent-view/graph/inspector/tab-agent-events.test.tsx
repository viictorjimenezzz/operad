import { TabAgentEvents } from "@/components/agent-view/graph/inspector/tab-agent-events";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockUseAgentEvents = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/use-runs", () => ({
  useAgentEvents: mockUseAgentEvents,
}));

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getTotalSize: () => count * 32,
    getVirtualItems: () =>
      Array.from({ length: Math.min(count, 20) }, (_, i) => ({
        index: i,
        size: 32,
        start: i * 32,
      })),
  }),
}));

function makeAgentEvent(index: number) {
  return {
    type: "agent_event" as const,
    run_id: "run-1",
    agent_path: "Root.leaf",
    kind: "end" as const,
    input: null,
    output: null,
    started_at: 1_700_000_000 + index,
    finished_at: null,
    metadata: {},
    error: null,
  };
}

function wrapper(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  cleanup();
});

describe("TabAgentEvents", () => {
  beforeEach(() => {
    mockUseAgentEvents.mockReturnValue({ isLoading: false, data: { run_id: "run-1", events: [] } });
  });

  it("shows empty state when no events", () => {
    render(wrapper(<TabAgentEvents runId="run-1" agentPath="Root.leaf" />));
    expect(screen.getByText(/no agent events recorded/i)).toBeTruthy();
  });

  it("renders a virtualized event list container when events are present", () => {
    const events = Array.from({ length: 50 }, (_, i) => makeAgentEvent(i));
    mockUseAgentEvents.mockReturnValue({ isLoading: false, data: { run_id: "run-1", events } });
    render(wrapper(<TabAgentEvents runId="run-1" agentPath="Root.leaf" />));
    expect(screen.getByLabelText("agent event rows")).toBeTruthy();
  });

  it("shows tail chip and show-all button when events exceed 200", () => {
    const events = Array.from({ length: 250 }, (_, i) => makeAgentEvent(i));
    mockUseAgentEvents.mockReturnValue({ isLoading: false, data: { run_id: "run-1", events } });
    render(wrapper(<TabAgentEvents runId="run-1" agentPath="Root.leaf" />));
    expect(screen.getByText(/showing last 200 of 250/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /show all/i })).toBeTruthy();
  });

  it("shows loading state", () => {
    mockUseAgentEvents.mockReturnValue({ isLoading: true, data: undefined });
    render(wrapper(<TabAgentEvents runId="run-1" agentPath="Root.leaf" />));
    expect(screen.getByText(/loading events/i)).toBeTruthy();
  });
});
