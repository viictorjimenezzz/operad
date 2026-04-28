import { computeAlgorithmKpis } from "@/lib/algorithm-kpis";
import type { RunSummary } from "@/lib/types";
import { describe, expect, it } from "vitest";

function makeRun(overrides: Partial<RunSummary>): RunSummary {
  return {
    run_id: "test-run",
    started_at: 0,
    last_event_at: 0,
    state: "ended",
    has_graph: false,
    is_algorithm: true,
    algorithm_path: null,
    algorithm_kinds: [],
    algorithm_class: null,
    root_agent_path: null,
    script: null,
    event_counts: {},
    event_total: 0,
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
    synthetic: false,
    parent_run_id: null,
    ...overrides,
  } as RunSummary;
}

describe("computeAlgorithmKpis()", () => {
  it("returns [] for unknown class", () => {
    expect(computeAlgorithmKpis(makeRun({ algorithm_class: null }))).toEqual([]);
    expect(computeAlgorithmKpis(makeRun({ algorithm_class: "Unknown" }))).toEqual([]);
  });

  describe("Sweep", () => {
    it("returns cells and best", () => {
      const run = makeRun({
        algorithm_class: "Sweep",
        generations: [
          { gen_index: 0, best: 0.8, mean: 0.7, scores: [0.8, 0.7], survivor_indices: [], op_attempt_counts: {}, op_success_counts: {}, timestamp: null },
          { gen_index: 1, best: 0.9, mean: 0.85, scores: [0.9, 0.85], survivor_indices: [], op_attempt_counts: {}, op_success_counts: {}, timestamp: null },
        ],
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis).toHaveLength(2);
      expect(kpis[0]).toMatchObject({ label: "cells", value: "2" });
      expect(kpis[1]).toMatchObject({ label: "best", value: "0.900" });
    });

    it("shows - for best when no scores", () => {
      const run = makeRun({ algorithm_class: "Sweep", generations: [] });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[1]).toMatchObject({ label: "best", value: "-" });
    });
  });

  describe("Beam", () => {
    it("returns K and top", () => {
      const run = makeRun({
        algorithm_class: "Beam",
        candidates: [
          { iter_index: null, candidate_index: 0, score: 0.75, text: null, timestamp: null },
          { iter_index: null, candidate_index: 1, score: 0.92, text: null, timestamp: null },
          { iter_index: null, candidate_index: 2, score: 0.61, text: null, timestamp: null },
        ],
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "K", value: "3" });
      expect(kpis[1]).toMatchObject({ label: "top", value: "0.920" });
    });

    it("shows - for top when no candidates", () => {
      const run = makeRun({ algorithm_class: "Beam", candidates: [] });
      expect(computeAlgorithmKpis(run)[1]).toMatchObject({ label: "top", value: "-" });
    });
  });

  describe("Debate", () => {
    it("returns rounds and consensus (std dev of last round scores)", () => {
      const run = makeRun({
        algorithm_class: "Debate",
        rounds: [
          { round_index: 0, scores: [0.5, 0.6], timestamp: null },
          { round_index: 1, scores: [0.8, 0.8], timestamp: null },
        ],
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "rounds", value: "2" });
      expect(kpis[1].label).toBe("consensus");
      expect(parseFloat(kpis[1].value)).toBeCloseTo(0, 3);
    });

    it("shows - for consensus with no rounds", () => {
      const run = makeRun({ algorithm_class: "Debate", rounds: [] });
      expect(computeAlgorithmKpis(run)[1]).toMatchObject({ label: "consensus", value: "-" });
    });
  });

  describe("EvoGradient", () => {
    it("returns gens, pop, and best", () => {
      const run = makeRun({
        algorithm_class: "EvoGradient",
        generations: [
          { gen_index: 0, best: 0.6, mean: 0.5, scores: [0.6, 0.5, 0.4], survivor_indices: [], op_attempt_counts: {}, op_success_counts: {}, timestamp: null },
          { gen_index: 1, best: 0.75, mean: 0.65, scores: [0.75, 0.65, 0.55], survivor_indices: [], op_attempt_counts: {}, op_success_counts: {}, timestamp: null },
        ],
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "gens", value: "2" });
      expect(kpis[1]).toMatchObject({ label: "pop", value: "3" });
      expect(kpis[2]).toMatchObject({ label: "best", value: "0.750" });
    });
  });

  describe("Trainer", () => {
    it("returns epochs and best_val", () => {
      const run = makeRun({
        algorithm_class: "Trainer",
        batches: [
          { kind: "train", batch_index: 0, batch_size: 32, duration_ms: null, epoch: 0, timestamp: null },
          { kind: "train", batch_index: 1, batch_size: 32, duration_ms: null, epoch: 2, timestamp: null },
        ],
        metrics: { val_loss: 0.42 },
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "epochs", value: "2" });
      expect(kpis[1]).toMatchObject({ label: "best_val", value: "0.420" });
    });

    it("omits lr when not in metrics", () => {
      const run = makeRun({
        algorithm_class: "Trainer",
        batches: [],
        metrics: { val_loss: 0.3 },
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis.find((k) => k.label === "lr")).toBeUndefined();
    });

    it("includes lr when present in metrics", () => {
      const run = makeRun({
        algorithm_class: "Trainer",
        batches: [],
        metrics: { val_loss: 0.3, lr: 0.001 },
      });
      const kpis = computeAlgorithmKpis(run);
      const lr = kpis.find((k) => k.label === "lr");
      expect(lr).toBeDefined();
      expect(lr?.value).toBe("1.00e-3");
    });
  });

  describe("OPRO", () => {
    it("returns iters and best", () => {
      const run = makeRun({
        algorithm_class: "OPRO",
        iterations: [
          { iter_index: 0, phase: null, score: 0.5, text: null, metadata: {}, timestamp: null },
          { iter_index: 1, phase: null, score: 0.7, text: null, metadata: {}, timestamp: null },
        ],
        algorithm_terminal_score: 0.7,
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "iters", value: "2" });
      expect(kpis[1]).toMatchObject({ label: "best", value: "0.700" });
    });
  });

  describe("SelfRefine", () => {
    it("returns iters and best", () => {
      const run = makeRun({
        algorithm_class: "SelfRefine",
        iterations: [
          { iter_index: 0, phase: null, score: 0.6, text: null, metadata: {}, timestamp: null },
        ],
        algorithm_terminal_score: 0.6,
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "iters", value: "1" });
      expect(kpis[1]).toMatchObject({ label: "best", value: "0.600" });
    });
  });

  describe("AutoResearcher", () => {
    it("counts plan-phase iterations as attempts", () => {
      const run = makeRun({
        algorithm_class: "AutoResearcher",
        iterations: [
          { iter_index: 0, phase: "plan", score: null, text: null, metadata: {}, timestamp: null },
          { iter_index: 1, phase: "execute", score: null, text: null, metadata: {}, timestamp: null },
          { iter_index: 2, phase: "plan", score: null, text: null, metadata: {}, timestamp: null },
        ],
        algorithm_terminal_score: 0.85,
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "attempts", value: "2" });
      expect(kpis[1]).toMatchObject({ label: "best", value: "0.850" });
    });
  });

  describe("TalkerReasoner", () => {
    it("returns turns", () => {
      const run = makeRun({
        algorithm_class: "TalkerReasoner",
        iterations: [
          { iter_index: 0, phase: null, score: null, text: null, metadata: {}, timestamp: null },
          { iter_index: 1, phase: null, score: null, text: null, metadata: {}, timestamp: null },
          { iter_index: 2, phase: null, score: null, text: null, metadata: {}, timestamp: null },
        ],
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis).toHaveLength(1);
      expect(kpis[0]).toMatchObject({ label: "turns", value: "3" });
    });
  });

  describe("Verifier", () => {
    it("returns iters and acceptance rate", () => {
      const run = makeRun({
        algorithm_class: "Verifier",
        iterations: [
          { iter_index: 0, phase: "accepted", score: null, text: null, metadata: {}, timestamp: null },
          { iter_index: 1, phase: "rejected", score: null, text: null, metadata: {}, timestamp: null },
          { iter_index: 2, phase: "accepted", score: null, text: null, metadata: {}, timestamp: null },
          { iter_index: 3, phase: "rejected", score: null, text: null, metadata: {}, timestamp: null },
        ],
      });
      const kpis = computeAlgorithmKpis(run);
      expect(kpis[0]).toMatchObject({ label: "iters", value: "4" });
      expect(kpis[1]).toMatchObject({ label: "acc", value: "50%" });
    });

    it("shows - for acc when no iterations", () => {
      const run = makeRun({ algorithm_class: "Verifier", iterations: [] });
      expect(computeAlgorithmKpis(run)[1]).toMatchObject({ label: "acc", value: "-" });
    });
  });
});
