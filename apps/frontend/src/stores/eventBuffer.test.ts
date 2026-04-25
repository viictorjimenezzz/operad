import type { AgentEventEnvelope, AlgoEventEnvelope } from "@/lib/types";
import { eventBufferLimits, useEventBufferStore } from "@/stores/eventBuffer";
import { beforeEach, describe, expect, it } from "vitest";

function agentEvent(runId: string, ts: number): AgentEventEnvelope {
  return {
    type: "agent_event",
    run_id: runId,
    agent_path: "Root",
    kind: "end",
    input: null,
    output: null,
    started_at: ts,
    finished_at: ts + 1,
    metadata: {},
    error: null,
  };
}

function generationEvent(runId: string, genIdx: number, scores: number[]): AlgoEventEnvelope {
  return {
    type: "algo_event",
    run_id: runId,
    algorithm_path: "EvoGradient",
    kind: "generation",
    payload: { gen_index: genIdx, population_scores: scores },
    started_at: genIdx,
    finished_at: genIdx + 1,
    metadata: {},
  };
}

beforeEach(() => {
  useEventBufferStore.getState().clear();
});

describe("useEventBufferStore", () => {
  it("partitions events by run_id", () => {
    useEventBufferStore.getState().ingest(agentEvent("run-a", 1));
    useEventBufferStore.getState().ingest(agentEvent("run-b", 2));
    useEventBufferStore.getState().ingest(agentEvent("run-a", 3));

    const a = useEventBufferStore.getState().eventsByRun.get("run-a") ?? [];
    const b = useEventBufferStore.getState().eventsByRun.get("run-b") ?? [];
    expect(a).toHaveLength(2);
    expect(b).toHaveLength(1);
  });

  it("trims to MAX_EVENTS_PER_RUN per run", () => {
    const limit = eventBufferLimits.maxEventsPerRun;
    for (let i = 0; i < limit + 10; i++) {
      useEventBufferStore.getState().ingest(agentEvent("run-a", i));
    }
    const buf = useEventBufferStore.getState().eventsByRun.get("run-a") ?? [];
    expect(buf.length).toBe(limit);
    // Oldest events were dropped.
    expect(buf[0]?.started_at).toBe(10);
    expect(buf[buf.length - 1]?.started_at).toBe(limit + 9);
  });

  it("derives liveGenerations from generation events", () => {
    useEventBufferStore.getState().ingest(generationEvent("run-a", 0, [0.1, 0.2, 0.3]));
    useEventBufferStore.getState().ingest(generationEvent("run-a", 1, [0.5, 0.7]));
    const gens = useEventBufferStore.getState().liveGenerations;
    expect(gens).toHaveLength(2);
    expect(gens[0]?.best).toBeCloseTo(0.3);
    expect(gens[0]?.mean).toBeCloseTo(0.2);
    expect(gens[1]?.best).toBeCloseTo(0.7);
  });

  it("trims liveGenerations to its cap", () => {
    const limit = eventBufferLimits.maxLiveGenerations;
    for (let i = 0; i < limit + 5; i++) {
      useEventBufferStore.getState().ingest(generationEvent("r", i, [Math.random()]));
    }
    expect(useEventBufferStore.getState().liveGenerations.length).toBe(limit);
  });

  it("clear(runId) removes only that run", () => {
    useEventBufferStore.getState().ingest(agentEvent("run-a", 1));
    useEventBufferStore.getState().ingest(agentEvent("run-b", 2));
    useEventBufferStore.getState().clear("run-a");
    expect(useEventBufferStore.getState().eventsByRun.has("run-a")).toBe(false);
    expect(useEventBufferStore.getState().eventsByRun.has("run-b")).toBe(true);
  });

  it("tracks latestEnvelope across types", () => {
    const slotEnv = {
      type: "slot_occupancy" as const,
      snapshot: [{ backend: "openai", host: "x" }],
    };
    useEventBufferStore.getState().ingest(slotEnv);
    expect(useEventBufferStore.getState().latestEnvelope).toEqual(slotEnv);
  });
});
