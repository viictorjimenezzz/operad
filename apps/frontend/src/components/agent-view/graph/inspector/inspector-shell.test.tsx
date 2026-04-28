import { InspectorShell } from "@/components/agent-view/graph/inspector/inspector-shell";
import type { IoGraphResponse } from "@/lib/types";
import { useUIStore } from "@/stores";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hookMocks = vi.hoisted(() => ({
  useAgentMeta: vi.fn(),
  useAgentEvents: vi.fn(),
}));

vi.mock("@/hooks/use-runs", () => ({
  useAgentMeta: hookMocks.useAgentMeta,
  useAgentEvents: hookMocks.useAgentEvents,
}));

vi.mock("@/components/agent-view/graph/inspector/tab-agent-invocations", () => ({
  TabAgentInvocations: () => <div>invocations tab</div>,
}));
vi.mock("@/components/agent-view/graph/inspector/tab-agent-prompts", () => ({
  TabAgentPrompts: () => <div>prompts tab</div>,
}));
vi.mock("@/components/agent-view/graph/inspector/tab-fields", () => ({
  TabFields: () => <div>fields tab</div>,
}));

const baseMeta = {
  agent_path: "Root.leaf",
  class_name: "Leaf",
  kind: "leaf",
  hash_content: "abc123def456",
  role: "A test role",
  task: "A test task",
  rules: [],
  examples: [],
  config: null,
  input_schema: {
    key: "tests.Input",
    name: "Input",
    fields: [{ name: "text", type: "str", description: "Prompt text.", system: false }],
  },
  output_schema: {
    key: "tests.Output",
    name: "Output",
    fields: [{ name: "answer", type: "str", description: "Answer text.", system: false }],
  },
  forward_in_overridden: false,
  forward_out_overridden: false,
  trainable_paths: [],
  langfuse_search_url: null,
};

const ioGraph: IoGraphResponse = {
  root: null,
  nodes: [{ key: "InputType", name: "InputType", fields: [] }],
  edges: [
    {
      agent_path: "Root.leaf",
      class_name: "Leaf",
      kind: "leaf",
      from: "InputType",
      to: "InputType",
      composite_path: null,
    },
  ],
  composites: [],
};

function wrapper(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  cleanup();
});

describe("InspectorShell", () => {
  beforeEach(() => {
    hookMocks.useAgentMeta.mockReturnValue({ isLoading: false, data: baseMeta });
    hookMocks.useAgentEvents.mockReturnValue({ isLoading: false, data: { events: [] } });
    useUIStore.setState({
      graphSelection: { kind: "edge", agentPath: "Root.leaf" },
      graphInspectorTab: "overview",
    });
  });

  it("renders exactly four edge tabs", () => {
    render(wrapper(<InspectorShell runId="run-1" ioGraph={ioGraph} onClose={vi.fn()} />));
    expect(screen.getByRole("button", { name: "Overview" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Invocations" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Prompts" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Events" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /edit.*run/i })).toBeNull();
    expect(screen.queryByText(/^langfuse$/i)).toBeNull();
  });

  it("renders the schema overview tab by default", () => {
    render(wrapper(<InspectorShell runId="run-1" ioGraph={ioGraph} onClose={vi.fn()} />));
    expect(screen.getByText("tests.Input")).toBeTruthy();
    expect(screen.getByText("tests.Output")).toBeTruthy();
    expect(screen.getByText("text")).toBeTruthy();
    expect(screen.queryByText("hooks")).toBeNull();
  });

  it("switches to events tab on click", () => {
    render(wrapper(<InspectorShell runId="run-1" ioGraph={ioGraph} onClose={vi.fn()} />));
    fireEvent.click(screen.getByRole("button", { name: "Events" }));
    // empty events → empty state message (overview no longer visible)
    expect(screen.queryByText("tests.Input")).toBeNull();
    expect(screen.getByText(/no agent events recorded/i)).toBeTruthy();
  });

  it("shows node fields tab when a node is selected (no edge tabs)", () => {
    useUIStore.setState({ graphSelection: { kind: "node", nodeKey: "InputType" } });
    render(wrapper(<InspectorShell runId="run-1" ioGraph={ioGraph} onClose={vi.fn()} />));
    expect(screen.getByText("fields tab")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Overview" })).toBeNull();
  });

  it("shows langfuse chip when langfuse_search_url is present", () => {
    hookMocks.useAgentMeta.mockReturnValue({
      isLoading: false,
      data: { ...baseMeta, langfuse_search_url: "https://langfuse.example.com/search" },
    });
    render(wrapper(<InspectorShell runId="run-1" ioGraph={ioGraph} onClose={vi.fn()} />));
    const link = screen.getByRole("link", { name: /langfuse/i });
    expect(link).toBeTruthy();
    expect((link as HTMLAnchorElement).href).toContain("langfuse.example.com");
  });
});
