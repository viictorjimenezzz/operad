import type { RunSummary } from "@/lib/types";
import { normalizeSeriesForComparison } from "@/shared/charts/curve-overlay";
import { describe, expect, it } from "vitest";
import {
  buildCurve,
  buildPromptText,
  computeParetoFrontier,
  computeQuality,
  parseRunsParam,
  resolveComparisonRunIds,
  updateRunsSearch,
} from "./ExperimentsPage";

function makeRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "run-1",
    started_at: 1,
    last_event_at: 2,
    state: "ended",
    has_graph: false,
    is_algorithm: true,
    algorithm_path: "operad.algorithms.EvoGradient",
    algorithm_kinds: [],
    root_agent_path: null,
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
    algorithm_class: "EvoGradient",
    ...overrides,
  };
}

describe("Experiments helpers", () => {
  it("parseRunsParam dedupes, preserves order, and skips empties", () => {
    expect(parseRunsParam("run-a,,run-b,run-a, run-c ")).toEqual(["run-a", "run-b", "run-c"]);
  });

  it("URL ids take precedence over pinned ids", () => {
    expect(resolveComparisonRunIds("url-a,url-b", ["pin-1", "pin-2"])).toEqual(["url-a", "url-b"]);
    expect(resolveComparisonRunIds(null, ["pin-1", "pin-2", "pin-1"])).toEqual([
      "pin-1",
      "pin-2",
    ]);
  });

  it("updateRunsSearch sets and clears runs param", () => {
    const current = new URLSearchParams("foo=1");
    const withRuns = updateRunsSearch(current, ["a", "b", "a"]);
    expect(withRuns.get("runs")).toBe("a,b");
    expect(withRuns.get("foo")).toBe("1");

    const cleared = updateRunsSearch(withRuns, []);
    expect(cleared.get("runs")).toBeNull();
    expect(cleared.get("foo")).toBe("1");
  });

  it("selects curve adapter for Debate using round agreement", () => {
    const run = makeRun({ algorithm_class: "Debate" });
    const curve = buildCurve(run, {
      fitness: null,
      iterations: null,
      mutations: null,
      debate: [
        { round_index: 0, proposals: [], critiques: [], scores: [0.2, 0.8], timestamp: 1 },
        { round_index: 1, proposals: [], critiques: [], scores: [0.7, 0.7], timestamp: 2 },
      ],
    } as any);

    expect(curve.length).toBe(2);
    expect(curve[0]?.x).toBe(0);
    expect(curve[1]?.x).toBe(1);
  });

  it("normalizes heterogeneous curves by step index", () => {
    expect(
      normalizeSeriesForComparison(
        [
          { x: 10, y: 1 },
          { x: 20, y: 2 },
        ],
        true,
      ),
    ).toEqual([
      { x: 0, y: 1 },
      { x: 1, y: 2 },
    ]);
  });

  it("prompt fallback chain: iterations -> candidates -> debate", () => {
    const runWithCandidate = makeRun({
      candidates: [
        { iter_index: 0, candidate_index: 0, score: 0.4, text: "candidate", timestamp: 1 },
      ],
    });

    const fromIterations = buildPromptText(runWithCandidate, {
      fitness: null,
      mutations: null,
      debate: null,
      iterations: {
        iterations: [
          { iter_index: 0, phase: null, score: null, text: "", metadata: {} },
          { iter_index: 1, phase: null, score: null, text: "iter text", metadata: {} },
        ],
        max_iter: null,
        threshold: null,
        converged: null,
      },
    } as any);
    expect(fromIterations).toBe("iter text");

    const fromCandidates = buildPromptText(runWithCandidate, {
      fitness: null,
      mutations: null,
      debate: null,
      iterations: { iterations: [], max_iter: null, threshold: null, converged: null },
    } as any);
    expect(fromCandidates).toBe("candidate");

    const fromDebate = buildPromptText(makeRun(), {
      fitness: null,
      mutations: null,
      iterations: { iterations: [], max_iter: null, threshold: null, converged: null },
      debate: [
        {
          round_index: 0,
          critiques: [],
          scores: [0.1, 0.9],
          timestamp: 1,
          proposals: [
            { author: "a", content: "draft" },
            { author: "b", content: "winner" },
          ],
        },
      ],
    } as any);
    expect(fromDebate).toBe("winner");
  });

  it("quality normalization flips loss-based Trainer metric", () => {
    const trainer = makeRun({ algorithm_class: "Trainer" });
    const evo = makeRun({ algorithm_class: "EvoGradient" });
    expect(computeQuality(trainer, [{ x: 0, y: 0.2 }])).toBe(-0.2);
    expect(computeQuality(evo, [{ x: 0, y: 0.2 }])).toBe(0.2);
  });

  it("pareto frontier excludes dominated points and handles equal cost deterministically", () => {
    const frontier = computeParetoFrontier([
      { runId: "a", cost: 10, quality: 0.2 },
      { runId: "b", cost: 10, quality: 0.5 },
      { runId: "c", cost: 11, quality: 0.4 },
      { runId: "d", cost: 12, quality: 0.7 },
    ]);

    expect(frontier).toEqual(["b", "d"]);
  });
});
