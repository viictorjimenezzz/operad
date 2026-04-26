import { FilteredEvents } from "@/components/agent-view/drawer/views/events/filtered-events";
import type { AgentEventEnvelope, EventEnvelope } from "@/lib/types";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let mockAgentEvents: EventEnvelope[] = [];
let mockAgentEventsLoading = false;
let mockAgentEventsError: Error | null = null;
let mockLiveEvents: EventEnvelope[] = [];
let mockDrawerWidth = 480;
let mockLangfuseUrl: string | null = null;

vi.mock("@/hooks/use-runs", () => ({
  useAgentEvents: () => ({
    data: { run_id: "run-1", events: mockAgentEvents },
    isLoading: mockAgentEventsLoading,
    error: mockAgentEventsError,
  }),
  useManifest: () => ({ data: { langfuseUrl: mockLangfuseUrl } }),
}));

vi.mock("@/stores", () => ({
  useEventBufferStore: (selector: (state: { eventsByRun: Map<string, EventEnvelope[]> }) => unknown) =>
    selector({ eventsByRun: new Map([["run-1", mockLiveEvents]]) }),
}));

vi.mock("@/stores/ui", () => ({
  useUIStore: (selector: (state: { drawerWidth: number }) => unknown) =>
    selector({ drawerWidth: mockDrawerWidth }),
}));

function event(partial: Partial<AgentEventEnvelope>): AgentEventEnvelope {
  return {
    type: "agent_event",
    run_id: "run-1",
    agent_path: "Pipeline.stage_0",
    kind: "start",
    input: null,
    output: null,
    started_at: 10,
    finished_at: null,
    metadata: {},
    error: null,
    ...partial,
  };
}

describe("FilteredEvents", () => {
  beforeEach(() => {
    mockAgentEvents = [];
    mockAgentEventsLoading = false;
    mockAgentEventsError = null;
    mockLiveEvents = [];
    mockDrawerWidth = 480;
    mockLangfuseUrl = null;
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("merges archived and live events filtered by agent_path", () => {
    mockAgentEvents = [event({ kind: "start", input: { text: "q1" }, started_at: 1 })];
    mockLiveEvents = [
      event({ kind: "end", output: { answer: "done" }, started_at: 2, finished_at: 2.1 }),
      event({ agent_path: "Pipeline.other", kind: "end", output: { answer: "skip" }, started_at: 3 }),
    ];

    render(<FilteredEvents runId="run-1" payload={{ agentPath: "Pipeline.stage_0" }} />);

    expect(screen.getByText("2 events")).toBeTruthy();
  });

  it("supports kind + search filtering", () => {
    mockAgentEvents = [
      event({ kind: "start", input: { text: "hello" }, started_at: 1 }),
      event({
        kind: "error",
        error: { type: "RuntimeError", message: "boom" },
        started_at: 2,
        finished_at: 2.1,
      }),
    ];

    render(<FilteredEvents runId="run-1" payload={{ agentPath: "Pipeline.stage_0" }} />);

    fireEvent.click(screen.getByRole("button", { name: "error" }));
    expect(screen.getByText("1 events")).toBeTruthy();

    fireEvent.change(screen.getByPlaceholderText("search kind/path/preview"), {
      target: { value: "boom" },
    });
    expect(screen.getByText("1 events")).toBeTruthy();
  });

  it("shows live pulse and detail pane selection", () => {
    mockLiveEvents = [event({ kind: "end", output: { answer: "x" }, started_at: 2, finished_at: 2.1 })];

    const { container } = render(
      <FilteredEvents runId="run-1" payload={{ agentPath: "Pipeline.stage_0" }} />,
    );

    expect(container.querySelector(".animate-pulse.bg-ok")).toBeTruthy();
    const endButtons = screen.getAllByRole("button", { name: /end/i });
    const rowButton = endButtons[1];
    if (!rowButton) throw new Error("expected event row button");
    fireEvent.click(rowButton);
    expect(screen.getByText(/"kind": "end"/)).toBeTruthy();
  });

  it("shows invocation jump only when payload invocationId exists", () => {
    mockAgentEvents = [
      event({ kind: "start", started_at: 1, metadata: { invocation_id: "inv-1" } }),
      event({ kind: "end", started_at: 2, metadata: { invocation_id: "inv-1" }, finished_at: 2.1 }),
    ];

    const { rerender } = render(
      <FilteredEvents runId="run-1" payload={{ agentPath: "Pipeline.stage_0" }} />,
    );
    expect(screen.queryByText("jump")).toBeNull();

    rerender(
      <FilteredEvents
        runId="run-1"
        payload={{ agentPath: "Pipeline.stage_0", invocationId: "inv-1" }}
      />,
    );
    expect(screen.getByText("jump")).toBeTruthy();
    expect(screen.getByRole("option", { name: "invocation #1" })).toBeTruthy();
  });

  it("groups consecutive chunk events and toggles expansion", () => {
    mockAgentEvents = [
      event({ kind: "chunk", started_at: 1, output: { token: "a" }, metadata: { stream_id: "s-1" } }),
      event({ kind: "chunk", started_at: 1.1, output: { token: "b" }, metadata: { stream_id: "s-1" } }),
      event({ kind: "end", started_at: 1.2, finished_at: 1.3 }),
    ];

    render(<FilteredEvents runId="run-1" payload={{ agentPath: "Pipeline.stage_0" }} />);

    const toggle = screen.getByRole("button", { name: /expand chunk group/i });
    expect(toggle.textContent).toContain("show 2");
    fireEvent.click(toggle);
    expect(screen.getByText("#1")).toBeTruthy();
  });

  it("enables split mode when drawer is wide", () => {
    mockAgentEvents = [event({ kind: "start", started_at: 1 })];
    mockDrawerWidth = 720;
    mockLangfuseUrl = null;

    render(<FilteredEvents runId="run-1" payload={{ agentPath: "Pipeline.stage_0" }} />);

    expect(screen.getByText("Langfuse is not configured")).toBeTruthy();
  });
});
