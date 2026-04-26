import { ValueTimeline } from "@/components/agent-view/drawer/views/values/value-timeline";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEventBufferStore } from "@/stores/eventBuffer";
import { useUIStore } from "@/stores/ui";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const agentValuesMock = vi.fn();

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentValues: (...args: unknown[]) => agentValuesMock(...args),
  },
}));

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ValueTimeline", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    agentValuesMock.mockReset();
    useEventBufferStore.setState({ eventsByRun: new Map(), liveGenerations: [], latestEnvelope: null });
    useUIStore.setState({
      currentTab: "overview",
      eventKindFilter: "all",
      eventSearch: "",
      autoFollow: true,
      eventsFollow: true,
      sidebarCollapsed: false,
      drawer: null,
      drawerWidth: 480,
      selectedInvocationId: null,
      selectedInvocationAgentPath: null,
    });
  });

  it("loads values, switches side, and supports row actions", async () => {
    agentValuesMock.mockImplementation(async (_runId: string, _path: string, _attr: string, side: "in" | "out") => ({
      agent_path: "Root",
      attribute: "question",
      side,
      type: "str",
      values:
        side === "in"
          ? [
              { invocation_id: "Root:0", started_at: 10, value: "what is france" },
              { invocation_id: "Root:1", started_at: 11, value: "what is germany" },
            ]
          : [{ invocation_id: "Root:0", started_at: 10, value: "Paris" }],
    }));

    wrap(<ValueTimeline payload={{ agentPath: "Root", attr: "question", side: "in" }} runId="run-1" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "output" })).toBeTruthy());
    await waitFor(() => expect(screen.getAllByText("open").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText("output"));
    await waitFor(() => expect(agentValuesMock).toHaveBeenCalledWith("run-1", "Root", "question", "out"));
    await waitFor(() => expect(screen.getByRole("button", { name: "input" })).toBeTruthy());

    fireEvent.click(screen.getByText("input"));
    await waitFor(() => expect(screen.getAllByText("open").length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText("open")[0] as HTMLElement);
    expect(useUIStore.getState().drawer).toEqual({
      kind: "events",
      payload: { agentPath: "Root", invocationId: "Root:1" },
    });
    expect(useUIStore.getState().selectedInvocationId).toBe("Root:1");
  });

  it("merges live event-buffer values and deduplicates invocation ids", async () => {
    agentValuesMock.mockResolvedValue({
      agent_path: "Root",
      attribute: "question",
      side: "in",
      type: "str",
      values: [{ invocation_id: "Root:0", started_at: 10, value: "seed" }],
    });

    useEventBufferStore.setState({
      eventsByRun: new Map([
        [
          "run-1",
          [
            {
              type: "agent_event",
              run_id: "run-1",
              agent_path: "Root",
              kind: "end",
              input: { question: "live" },
              output: null,
              started_at: 12,
              finished_at: 12.2,
              metadata: {},
              error: null,
            },
          ],
        ],
      ]),
      liveGenerations: [],
      latestEnvelope: null,
    });

    wrap(<ValueTimeline payload={{ agentPath: "Root", attr: "question", side: "in" }} runId="run-1" />);

    await waitFor(() => {
      expect(screen.getAllByText(/live/i).length).toBeGreaterThan(0);
    });
    expect(screen.queryByText(/seed/i)).toBeNull();
  });

  it("supports similarity filter and structural diff", async () => {
    agentValuesMock.mockResolvedValue({
      agent_path: "Root",
      attribute: "answer",
      side: "out",
      type: "dict",
      values: [
        { invocation_id: "Root:0", started_at: 10, value: { a: 1, b: 2 } },
        { invocation_id: "Root:1", started_at: 11, value: { a: 1, b: 3 } },
      ],
    });

    wrap(<ValueTimeline payload={{ agentPath: "Root", attr: "answer", side: "out" }} runId="run-1" />);

    await waitFor(() => expect(screen.getByLabelText("select diff Root:0")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("select diff Root:0"));
    fireEvent.click(screen.getByLabelText("select diff Root:1"));

    expect(screen.getByText(/structural diff/i)).toBeTruthy();

  });

  it("flags categorical outlier and token estimate for strings", async () => {
    agentValuesMock.mockResolvedValue({
      agent_path: "Root",
      attribute: "question",
      side: "in",
      type: "str",
      values: [
        ...Array.from({ length: 20 }).map((_, index) => ({
          invocation_id: `Root:${index}`,
          started_at: index,
          value: "common sample text",
        })),
        { invocation_id: "Root:20", started_at: 21, value: "rare phrase sample" },
      ],
    });

    wrap(<ValueTimeline payload={{ agentPath: "Root", attr: "question", side: "in" }} runId="run-1" />);

    await waitFor(() => expect(screen.getAllByText(/rare phrase sample/i).length).toBeGreaterThan(0));
    expect(screen.getByText(/outlier/i)).toBeTruthy();
    expect(screen.getAllByText(/~4 tok/i).length).toBeGreaterThan(0);
  });
});
