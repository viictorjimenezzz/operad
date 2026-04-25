import {
  AgentEventEnvelope,
  AlgoEventEnvelope,
  CostUpdateEnvelope,
  Envelope,
  FitnessEntry,
  MutationsMatrix,
  ProgressSnapshot,
  RunSummary,
  SlotOccupancyEnvelope,
  StatsUpdateEnvelope,
} from "@/lib/types";
import { describe, expect, it } from "vitest";

describe("envelope schemas", () => {
  it("parses an agent_event with full metadata", () => {
    const raw = {
      type: "agent_event",
      run_id: "abcd",
      agent_path: "Pipeline.stage_0",
      kind: "end",
      input: { text: "hi" },
      output: { answer: "hello", prompt_tokens: 10, completion_tokens: 5 },
      started_at: 100,
      finished_at: 101,
      metadata: { is_root: true },
      error: null,
    };
    const parsed = AgentEventEnvelope.parse(raw);
    expect(parsed.kind).toBe("end");
    expect(parsed.metadata.is_root).toBe(true);
  });

  it("parses an algo_event generation", () => {
    const raw = {
      type: "algo_event",
      run_id: "x",
      algorithm_path: "EvoGradient",
      kind: "generation",
      payload: {
        gen_index: 0,
        population_scores: [0.1, 0.2, 0.3],
        survivor_indices: [2],
        op_attempt_counts: { mutate_role: 5 },
        op_success_counts: { mutate_role: 1 },
      },
      started_at: 0,
      finished_at: 1,
      metadata: {},
    };
    const parsed = AlgoEventEnvelope.parse(raw);
    expect(parsed.kind).toBe("generation");
    expect(parsed.payload.gen_index).toBe(0);
  });

  it("Envelope union discriminates on type", () => {
    const slot = SlotOccupancyEnvelope.parse({
      type: "slot_occupancy",
      snapshot: [{ backend: "openai", host: "api", concurrency_used: 2 }],
    });
    expect(slot.snapshot).toHaveLength(1);

    const cost = CostUpdateEnvelope.parse({
      type: "cost_update",
      totals: { abc: { prompt_tokens: 10, completion_tokens: 5, cost_usd: 0.001 } },
    });
    expect(cost.totals.abc?.cost_usd).toBe(0.001);

    const stats = StatsUpdateEnvelope.parse({
      type: "stats_update",
      stats: { runs_total: 3, event_total: 50 },
    });
    expect(stats.stats.runs_total).toBe(3);

    expect(() => Envelope.parse({ type: "agent_event", run_id: "x" })).toThrow();
  });
});

describe("RunSummary", () => {
  it("parses a minimal /runs/{id}/summary", () => {
    const summary = RunSummary.parse({
      run_id: "x",
      started_at: 100,
      last_event_at: 101,
      state: "running",
      has_graph: false,
      is_algorithm: true,
      algorithm_path: "EvoGradient",
      algorithm_kinds: ["generation"],
      root_agent_path: null,
      event_counts: { generation: 4 },
      event_total: 4,
      duration_ms: 1000,
      generations: [],
      iterations: [],
      rounds: [],
      candidates: [],
      batches: [],
      prompt_tokens: 0,
      completion_tokens: 0,
      error: null,
      algorithm_terminal_score: null,
    });
    expect(summary.algorithm_path).toBe("EvoGradient");
    expect(summary.cost).toBeUndefined();
  });
});

describe("panel shapes", () => {
  it("parses fitness rows", () => {
    expect(
      FitnessEntry.parse({
        gen_index: 0,
        best: 0.9,
        mean: 0.5,
        worst: 0.1,
        population_scores: [0.1, 0.5, 0.9],
        timestamp: 0,
      }).best,
    ).toBe(0.9);
  });

  it("parses mutations matrix", () => {
    const m = MutationsMatrix.parse({
      gens: [0, 1],
      ops: ["a"],
      success: [[1, 2]],
      attempts: [[3, 4]],
    });
    expect(m.ops).toEqual(["a"]);
  });

  it("parses progress snapshot", () => {
    const p = ProgressSnapshot.parse({
      epoch: 1,
      epochs_total: 5,
      batch: 2,
      batches_total: null,
      elapsed_s: 1.5,
      rate_batches_per_s: 0,
      eta_s: null,
      finished: false,
    });
    expect(p.epochs_total).toBe(5);
  });
});
