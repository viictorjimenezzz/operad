import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { InvocationsTable } from "@/components/agent-view/metadata/invocations-table";
import { useUIStore } from "@/stores/ui";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

afterEach(() => cleanup());

describe("HashChip", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("uses deterministic color for same hash", () => {
    const { rerender } = render(<HashChip hash="abc123" />);
    const first = screen.getByRole("button", { name: /copy hash/i });
    const firstBg = first.style.backgroundColor;

    rerender(<HashChip hash="abc123" />);
    const second = screen.getByRole("button", { name: /copy hash/i });

    expect(second.style.backgroundColor).toBe(firstBg);
  });

  it("copies hash and shows inline copied feedback", async () => {
    render(<HashChip hash="abcdef123456" />);
    const button = screen.getByRole("button", { name: /copy hash/i });
    fireEvent.click(button);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("abcdef123456");
    await vi.waitFor(() => {
      expect(screen.getByText("copied")).toBeTruthy();
    });
  });
});

describe("InvocationsTable", () => {
  beforeEach(() => {
    useUIStore.setState({
      currentTab: "overview",
      eventKindFilter: "all",
      eventSearch: "",
      autoFollow: true,
      eventsFollow: true,
      sidebarCollapsed: false,
      drawer: null,
      drawerWidth: 420,
    });
  });

  it("renders waiting empty state with no invocations", () => {
    render(
      <InvocationsTable
        summary={{
          run_id: "run-1",
          started_at: 1,
          last_event_at: 1,
          state: "running",
          has_graph: true,
          is_algorithm: false,
          algorithm_path: null,
          algorithm_kinds: [],
          root_agent_path: "Pipeline",
          script: "demo.py",
          event_counts: {},
          event_total: 0,
          duration_ms: 0,
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
        }}
        invocations={{ agent_path: "Pipeline", invocations: [] }}
      />,
    );

    expect(screen.getByText("waiting for first invocation")).toBeTruthy();
  });

  it("dispatches drawer payloads for row click and diff action", () => {
    const openDrawer = vi.fn();
    useUIStore.setState((s) => ({ ...s, openDrawer }));

    render(
      <InvocationsTable
        summary={{
          run_id: "run-2",
          started_at: 1,
          last_event_at: 1,
          state: "ended",
          has_graph: true,
          is_algorithm: false,
          algorithm_path: null,
          algorithm_kinds: [],
          root_agent_path: "Pipeline",
          script: "demo.py",
          event_counts: {},
          event_total: 2,
          duration_ms: 2000,
          generations: [],
          iterations: [],
          rounds: [],
          candidates: [],
          batches: [],
          prompt_tokens: 10,
          completion_tokens: 3,
          error: null,
          algorithm_terminal_score: null,
          synthetic: false,
          parent_run_id: null,
          algorithm_class: null,
        }}
        invocations={{
          agent_path: "Pipeline.stage_0",
          invocations: [
            {
              id: "inv-1",
              started_at: 10,
              latency_ms: 800,
              prompt_tokens: 10,
              completion_tokens: 3,
              hash_prompt: "p1",
              status: "ok",
            },
            {
              id: "inv-2",
              started_at: 20,
              latency_ms: 6000,
              prompt_tokens: 11,
              completion_tokens: 4,
              hash_prompt: "p2",
              status: "error",
              error: "Error: boom",
            },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByTestId("invocation-row-1"));
    expect(openDrawer).toHaveBeenCalledWith("events", {
      agentPath: "Pipeline.stage_0",
      invocationId: "inv-2",
      hashPrompt: "p2",
    });

    const diffButtons = screen.getAllByRole("button", { name: "diff" });
    const secondDiff = diffButtons[1];
    if (!secondDiff) throw new Error("expected second diff button");
    fireEvent.click(secondDiff);
    expect(openDrawer).toHaveBeenCalledWith("events", {
      agentPath: "Pipeline.stage_0",
      mode: "prompt-diff",
      invocationId: "inv-2",
      prevInvocationId: "inv-1",
      hashPrompt: "p2",
    });
  });

  it("renders latency and error status", () => {
    render(
      <InvocationsTable
        summary={{
          run_id: "run-3",
          started_at: 1,
          last_event_at: 1,
          state: "ended",
          has_graph: true,
          is_algorithm: false,
          algorithm_path: null,
          algorithm_kinds: [],
          root_agent_path: "Pipeline",
          script: "demo.py",
          event_counts: {},
          event_total: 1,
          duration_ms: 1000,
          generations: [],
          iterations: [],
          rounds: [],
          candidates: [],
          batches: [],
          prompt_tokens: 10,
          completion_tokens: 3,
          error: null,
          algorithm_terminal_score: null,
          synthetic: false,
          parent_run_id: null,
          algorithm_class: null,
        }}
        invocations={{
          agent_path: "Pipeline.stage_0",
          invocations: [
            {
              id: "inv-1",
              started_at: 10,
              latency_ms: 6000,
              prompt_tokens: 10,
              completion_tokens: 3,
              hash_prompt: "p1",
              status: "error",
              error: "Error: timeout",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("6.0s")).toBeTruthy();
    expect(screen.getByText("error")).toBeTruthy();
  });
});
