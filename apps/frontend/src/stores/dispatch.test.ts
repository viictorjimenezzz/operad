import { dispatchEnvelope, useEventBufferStore, useStatsStore } from "@/stores";
import { beforeEach, describe, expect, it } from "vitest";

beforeEach(() => {
  useEventBufferStore.getState().clear();
  useStatsStore.setState({ slotOccupancy: [], costTotals: {}, globalStats: null });
});

describe("dispatchEnvelope()", () => {
  it("routes agent_event into eventBuffer", () => {
    dispatchEnvelope({
      type: "agent_event",
      run_id: "x",
      agent_path: "Root",
      kind: "start",
      input: null,
      output: null,
      started_at: 1,
      finished_at: null,
      metadata: {},
      error: null,
    });
    expect(useEventBufferStore.getState().eventsByRun.get("x")).toHaveLength(1);
  });

  it("routes slot_occupancy into stats slots", () => {
    dispatchEnvelope({
      type: "slot_occupancy",
      snapshot: [{ backend: "openai", host: "api", concurrency_used: 3 }],
    });
    expect(useStatsStore.getState().slotOccupancy).toHaveLength(1);
  });

  it("routes cost_update into stats costTotals", () => {
    dispatchEnvelope({
      type: "cost_update",
      totals: { r1: { prompt_tokens: 10, completion_tokens: 5, cost_usd: 0.001 } },
    });
    expect(useStatsStore.getState().costTotals.r1?.cost_usd).toBe(0.001);
  });

  it("routes stats_update into stats globalStats", () => {
    dispatchEnvelope({
      type: "stats_update",
      stats: {
        runs_total: 5,
        runs_running: 2,
        runs_ended: 3,
        runs_error: 0,
        runs_algorithm: 4,
        runs_agent: 1,
        event_total: 100,
        prompt_tokens: 0,
        completion_tokens: 0,
      },
    });
    expect(useStatsStore.getState().globalStats?.runs_total).toBe(5);
  });
});
