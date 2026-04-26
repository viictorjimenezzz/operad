import {
  ChunkReplay,
  buildReplayInvocations,
  mergeChunkEvents,
} from "@/components/agent-view/insights/chunk-replay";
import { useEventBufferStore } from "@/stores/eventBuffer";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const useAgentEventsMock = vi.fn();

vi.mock("@/hooks/use-runs", () => ({
  useAgentEvents: (...args: unknown[]) => useAgentEventsMock(...args),
}));

function makeInvocation(overrides: Record<string, unknown>) {
  return {
    id: "Root:0",
    started_at: 1,
    finished_at: 2,
    latency_ms: null,
    prompt_tokens: null,
    completion_tokens: null,
    cost_usd: null,
    hash_model: null,
    hash_prompt: "p",
    hash_graph: null,
    hash_input: "i",
    hash_output_schema: null,
    hash_config: null,
    hash_content: "h",
    status: "ok" as const,
    error: null,
    langfuse_url: null,
    script: null,
    backend: null,
    model: null,
    renderer: null,
    ...overrides,
  };
}

describe("ChunkReplay", () => {
  beforeEach(() => {
    useAgentEventsMock.mockReset();
    useEventBufferStore.setState({
      eventsByRun: new Map(),
      liveGenerations: [],
      latestEnvelope: null,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("merges archived + live chunks and deduplicates by signature", () => {
    const sharedChunk = {
      type: "agent_event" as const,
      run_id: "run-1",
      agent_path: "Root",
      kind: "chunk" as const,
      input: null,
      output: null,
      started_at: 1,
      finished_at: null,
      metadata: { chunk_index: 0, text: "Hello" },
      error: null,
    };
    const merged = mergeChunkEvents({
      runId: "run-1",
      agentPath: "Root",
      archivedEvents: [sharedChunk],
      liveEvents: [sharedChunk],
    });
    expect(merged).toHaveLength(1);
    expect(merged[0]?.text).toBe("Hello");
  });

  it("assigns chunks to invocation windows and replays with timers", () => {
    vi.useFakeTimers();

    useAgentEventsMock.mockReturnValue({
      data: {
        run_id: "run-1",
        events: [
          {
            type: "agent_event",
            run_id: "run-1",
            agent_path: "Root",
            kind: "chunk",
            input: null,
            output: null,
            started_at: 10,
            finished_at: null,
            metadata: { chunk_index: 0, text: "Hi " },
            error: null,
          },
          {
            type: "agent_event",
            run_id: "run-1",
            agent_path: "Root",
            kind: "chunk",
            input: null,
            output: null,
            started_at: 10.2,
            finished_at: null,
            metadata: { chunk_index: 1, text: "there" },
            error: null,
          },
        ],
      },
      isLoading: false,
      error: null,
    });

    render(
      <ChunkReplay
        runId="run-1"
        agentPath="Root"
        invocations={[
          makeInvocation({
            id: "Root:0",
            started_at: 9.9,
            finished_at: 11,
            input: { q: "hello" },
          }),
        ]}
      />,
    );

    expect(screen.getByText("replay")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "play" }));

    act(() => {
      vi.advanceTimersByTime(10);
    });
    expect(screen.getByText(/Hi/)).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(220);
    });
    expect(screen.getByText(/Hi there/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "reset" }));
    expect(screen.queryByText(/Hi there/)).toBeNull();
  });

  it("supports fast mode and invocation grouping", () => {
    const replayInvocations = buildReplayInvocations({
      runId: "run-1",
      agentPath: "Root",
      invocations: [
        makeInvocation({
          id: "Root:0",
          started_at: 1,
          finished_at: 2,
        }),
        makeInvocation({
          id: "Root:1",
          started_at: 3,
          finished_at: 4,
        }),
      ],
      archivedEvents: [
        {
          type: "agent_event",
          run_id: "run-1",
          agent_path: "Root",
          kind: "chunk",
          input: null,
          output: null,
          started_at: 1.2,
          finished_at: null,
          metadata: { chunk_index: 0, text: "A" },
          error: null,
        },
        {
          type: "agent_event",
          run_id: "run-1",
          agent_path: "Root",
          kind: "chunk",
          input: null,
          output: null,
          started_at: 3.1,
          finished_at: null,
          metadata: { chunk_index: 0, text: "B" },
          error: null,
        },
      ],
      liveEvents: [],
    });
    expect(replayInvocations).toHaveLength(2);
    expect(replayInvocations[0]?.chunks[0]?.text).toBe("A");
    expect(replayInvocations[1]?.chunks[0]?.text).toBe("B");
  });
});
