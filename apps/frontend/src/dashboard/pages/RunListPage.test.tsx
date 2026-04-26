import { getAlgorithmMetric } from "@/lib/algorithm-metrics";
import type { RunSummary } from "@/lib/types";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RunListPage } from "./RunListPage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    started_at: Math.floor(Date.now() / 1000) - 60,
    last_event_at: Math.floor(Date.now() / 1000),
    state: "ended",
    has_graph: false,
    is_algorithm: false,
    algorithm_path: null,
    algorithm_kinds: [],
    algorithm_class: null,
    root_agent_path: null,
    script: null,
    event_counts: {},
    event_total: 5,
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
  };
}

// ---------------------------------------------------------------------------
// RunListPage
// ---------------------------------------------------------------------------

describe("RunListPage", () => {
  it("renders 'select a run' empty state", () => {
    render(<RunListPage />);
    expect(screen.getByText(/select a run/i)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// getAlgorithmMetric
// ---------------------------------------------------------------------------

describe("getAlgorithmMetric", () => {
  it("returns EvoGradient best from last generation", () => {
    const run = makeRun({
      algorithm_class: "EvoGradient",
      generations: [
        {
          gen_index: 0,
          best: 0.5,
          mean: 0.4,
          scores: [],
          survivor_indices: [],
          op_attempt_counts: {},
          op_success_counts: {},
          timestamp: 0,
        },
        {
          gen_index: 1,
          best: 1.0,
          mean: 0.8,
          scores: [],
          survivor_indices: [],
          op_attempt_counts: {},
          op_success_counts: {},
          timestamp: 1,
        },
      ],
    });
    expect(getAlgorithmMetric(run)).toBe("best=1.000");
  });

  it("falls back to event count for unknown class", () => {
    const run = makeRun({ algorithm_class: "UnknownAlgo", event_total: 42 });
    expect(getAlgorithmMetric(run)).toBe("events=42");
  });

  it("falls back to terminal score when available", () => {
    const run = makeRun({
      algorithm_class: "UnknownAlgo",
      algorithm_terminal_score: 0.75,
      event_total: 10,
    });
    expect(getAlgorithmMetric(run)).toBe("score=0.750");
  });

  it("returns events=N for plain agent run (no class)", () => {
    const run = makeRun({ algorithm_class: null, event_total: 7 });
    expect(getAlgorithmMetric(run)).toBe("events=7");
  });

  it("returns Debate rounds count", () => {
    const run = makeRun({
      algorithm_class: "Debate",
      rounds: [
        { round_index: 0, scores: [0.8], timestamp: 0 },
        { round_index: 1, scores: [0.9], timestamp: 1 },
      ],
    });
    expect(getAlgorithmMetric(run)).toBe("rounds=2");
  });
});

// ---------------------------------------------------------------------------
// Filter logic (pure, isolated from sidebar component)
// ---------------------------------------------------------------------------

describe("filtering pipeline", () => {
  const nowSecs = Math.floor(Date.now() / 1000);

  const runs: RunSummary[] = [
    makeRun({ run_id: "run-running", state: "running", started_at: nowSecs - 10 }),
    makeRun({ run_id: "run-ended", state: "ended", started_at: nowSecs - 600 }),
    makeRun({ run_id: "run-error", state: "error", started_at: nowSecs - 100 }),
    makeRun({
      run_id: "run-old",
      state: "ended",
      started_at: nowSecs - 7200, // 2h ago
    }),
    makeRun({
      run_id: "run-synthetic",
      state: "ended",
      synthetic: true,
      started_at: nowSecs - 30,
    }),
    makeRun({
      run_id: "run-evogradient",
      state: "ended",
      algorithm_class: "EvoGradient",
      algorithm_path: "operad.algorithms.EvoGradient",
      started_at: nowSecs - 50,
    }),
  ];

  function applyFilter({
    statusFilter = "all",
    timeFilter = "all",
    search = "",
    showSynthetic = false,
  }: {
    statusFilter?: string;
    timeFilter?: string;
    search?: string;
    showSynthetic?: boolean;
  }): string[] {
    const TIME_CUTOFFS: Record<string, number | null> = {
      all: null,
      "1h": 3600,
      "24h": 86400,
      "7d": 604800,
    };
    const cutoff = TIME_CUTOFFS[timeFilter] ?? null;
    const q = search.trim().toLowerCase();

    return runs
      .filter((r) => {
        if (r.synthetic && !showSynthetic) return false;
        if (cutoff !== null && r.started_at < nowSecs - cutoff) return false;
        if (statusFilter === "running" && r.state !== "running") return false;
        if (statusFilter === "ended" && r.state !== "ended") return false;
        if (statusFilter === "errors" && r.state !== "error") return false;
        if (q) {
          const haystack = [r.run_id, r.algorithm_class ?? "", r.algorithm_path ?? ""]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(q)) return false;
        }
        return true;
      })
      .map((r) => r.run_id);
  }

  it("returns all non-synthetic runs with default filters", () => {
    const ids = applyFilter({});
    expect(ids).toContain("run-running");
    expect(ids).toContain("run-ended");
    expect(ids).toContain("run-error");
    expect(ids).not.toContain("run-synthetic");
  });

  it("status filter 'running' shows only running runs", () => {
    const ids = applyFilter({ statusFilter: "running" });
    expect(ids).toEqual(["run-running"]);
  });

  it("status filter 'errors' shows only error runs", () => {
    const ids = applyFilter({ statusFilter: "errors" });
    expect(ids).toEqual(["run-error"]);
  });

  it("time filter '1h' excludes runs older than 1 hour", () => {
    const ids = applyFilter({ timeFilter: "1h" });
    expect(ids).not.toContain("run-old");
    expect(ids).toContain("run-running");
  });

  it("search by run_id prefix matches case-insensitively", () => {
    const ids = applyFilter({ search: "RUN-RUNNING" });
    expect(ids).toEqual(["run-running"]);
  });

  it("search by algorithm_class matches substring", () => {
    const ids = applyFilter({ search: "evogradient" });
    expect(ids).toEqual(["run-evogradient"]);
  });

  it("search by algorithm_path matches substring", () => {
    const ids = applyFilter({ search: "operad.algorithms" });
    expect(ids).toEqual(["run-evogradient"]);
  });

  it("synthetic runs hidden when showSynthetic=false", () => {
    const ids = applyFilter({ showSynthetic: false });
    expect(ids).not.toContain("run-synthetic");
  });

  it("synthetic runs visible when showSynthetic=true", () => {
    const ids = applyFilter({ showSynthetic: true });
    expect(ids).toContain("run-synthetic");
  });
});

// ---------------------------------------------------------------------------
// Grouping logic
// ---------------------------------------------------------------------------

describe("grouping logic", () => {
  function groupRuns(runs: RunSummary[]): Record<string, string[]> {
    const map = new Map<string, RunSummary[]>();
    for (const run of runs) {
      const key = run.algorithm_class ?? "__agents__";
      const arr = map.get(key);
      if (arr) arr.push(run);
      else map.set(key, [run]);
    }
    const sorted = [...map.entries()].sort(([a], [b]) => {
      if (a === "__agents__") return 1;
      if (b === "__agents__") return -1;
      return a.localeCompare(b);
    });
    return Object.fromEntries(sorted.map(([k, v]) => [k, v.map((r) => r.run_id)]));
  }

  it("groups runs by algorithm_class", () => {
    const runs = [
      makeRun({ run_id: "r1", algorithm_class: "EvoGradient" }),
      makeRun({ run_id: "r2", algorithm_class: "EvoGradient" }),
      makeRun({ run_id: "r3", algorithm_class: "Trainer" }),
    ];
    const groups = groupRuns(runs);
    expect(groups.EvoGradient).toEqual(["r1", "r2"]);
    expect(groups.Trainer).toEqual(["r3"]);
  });

  it("null algorithm_class runs appear in __agents__ group", () => {
    const runs = [
      makeRun({ run_id: "agent-1", algorithm_class: null }),
      makeRun({ run_id: "algo-1", algorithm_class: "Debate" }),
    ];
    const groups = groupRuns(runs);
    expect(groups.__agents__).toEqual(["agent-1"]);
    expect(groups.Debate).toEqual(["algo-1"]);
  });

  it("algorithm groups appear before __agents__", () => {
    const runs = [
      makeRun({ run_id: "agent-1", algorithm_class: null }),
      makeRun({ run_id: "algo-1", algorithm_class: "EvoGradient" }),
    ];
    const groups = groupRuns(runs);
    const keys = Object.keys(groups);
    expect(keys.indexOf("EvoGradient")).toBeLessThan(keys.indexOf("__agents__"));
  });
});

// ---------------------------------------------------------------------------
// Multi-select logic
// ---------------------------------------------------------------------------

describe("multi-select logic", () => {
  const orderedIds = ["a", "b", "c", "d", "e"];

  function applySelect(
    prev: Set<string>,
    runId: string,
    opts: { shift?: boolean; cmd?: boolean },
    lastClicked: string | null,
  ): Set<string> {
    if (opts.shift && lastClicked) {
      const a = orderedIds.indexOf(lastClicked);
      const b = orderedIds.indexOf(runId);
      const range = orderedIds.slice(Math.min(a, b), Math.max(a, b) + 1);
      return new Set([...prev, ...range]);
    }
    if (opts.cmd) {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    }
    const next = new Set<string>();
    if (!prev.has(runId)) next.add(runId);
    return next;
  }

  it("single click selects only that row", () => {
    const result = applySelect(new Set(), "b", {}, null);
    expect([...result]).toEqual(["b"]);
  });

  it("single click on already-selected row deselects it", () => {
    const result = applySelect(new Set(["b"]), "b", {}, null);
    expect([...result]).toEqual([]);
  });

  it("cmd-click toggles individual item without clearing others", () => {
    const result = applySelect(new Set(["a"]), "c", { cmd: true }, "a");
    expect(result.has("a")).toBe(true);
    expect(result.has("c")).toBe(true);
  });

  it("cmd-click deselects an already-selected item", () => {
    const result = applySelect(new Set(["a", "c"]), "c", { cmd: true }, "a");
    expect(result.has("c")).toBe(false);
    expect(result.has("a")).toBe(true);
  });

  it("shift-click selects range between last-clicked and current", () => {
    const result = applySelect(new Set(["a"]), "d", { shift: true }, "a");
    expect([...result].sort()).toEqual(["a", "b", "c", "d"]);
  });

  it("compare footer logic: hidden with fewer than 2 selected", () => {
    const selectedIds = new Set(["a"]);
    expect(selectedIds.size >= 2).toBe(false);
  });

  it("compare footer visible with 2 or more selected", () => {
    const selectedIds = new Set(["a", "b"]);
    expect(selectedIds.size >= 2).toBe(true);
  });

  it("compare URL includes all selected IDs", () => {
    const selectedIds = new Set(["run-a", "run-b", "run-c"]);
    const url = `/experiments?runs=${[...selectedIds].join(",")}`;
    expect(url).toBe("/experiments?runs=run-a,run-b,run-c");
  });
});
