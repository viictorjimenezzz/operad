import { describe, expect, it } from "vitest";
import { appendDedupe, autoMerge, findPrimaryKey } from "./data-source";

describe("findPrimaryKey", () => {
  it("returns gen_index when present", () => {
    expect(findPrimaryKey({ gen_index: 0, best: 0.9 })).toBe("gen_index");
  });

  it("returns epoch when gen_index absent", () => {
    expect(findPrimaryKey({ epoch: 3, loss: 0.2 })).toBe("epoch");
  });

  it("returns iter_index when epoch absent", () => {
    expect(findPrimaryKey({ iter_index: 1, score: 0.7 })).toBe("iter_index");
  });

  it("returns null when no known key present", () => {
    expect(findPrimaryKey({ foo: "bar" })).toBeNull();
  });
});

describe("appendDedupe", () => {
  it("appends a new item", () => {
    const arr = [{ gen_index: 0, best: 0.8 }];
    const result = appendDedupe(arr, { gen_index: 1, best: 0.9 });
    expect(result).toHaveLength(2);
    expect((result[1] as { gen_index: number }).gen_index).toBe(1);
  });

  it("skips an item whose primary key already exists", () => {
    const arr = [{ gen_index: 0, best: 0.8 }];
    const result = appendDedupe(arr, { gen_index: 0, best: 0.85 });
    expect(result).toHaveLength(1);
  });

  it("deduplicates by epoch", () => {
    const arr = [{ epoch: 1, loss: 0.5 }];
    expect(appendDedupe(arr, { epoch: 1, loss: 0.4 })).toHaveLength(1);
    expect(appendDedupe(arr, { epoch: 2, loss: 0.4 })).toHaveLength(2);
  });

  it("keeps distinct phases for the same iter_index", () => {
    const arr = [{ iter_index: 1, phase: "refine", text: "draft" }];
    const result = appendDedupe(arr, { iter_index: 1, phase: "reflect", score: 0.9 });
    expect(result).toHaveLength(2);
  });

  it("deduplicates iteration rows by iter_index and phase", () => {
    const arr = [{ iter_index: 1, phase: "reflect", score: 0.8 }];
    const result = appendDedupe(arr, { iter_index: 1, phase: "reflect", score: 0.9 });
    expect(result).toHaveLength(1);
  });

  it("appends when no primary key (no dedup possible)", () => {
    const arr = [{ foo: "a" }];
    const result = appendDedupe(arr, { foo: "b" });
    expect(result).toHaveLength(2);
  });
});

describe("autoMerge", () => {
  it("appends a non-array delta into an array current state", () => {
    const current = [{ gen_index: 0, best: 0.8 }];
    const delta = { gen_index: 1, best: 0.9 };
    const result = autoMerge(current, delta) as unknown[];
    expect(result).toHaveLength(2);
  });

  it("deduplicates when current is array and delta has a matching primary key", () => {
    const current = [{ gen_index: 0, best: 0.8 }];
    const delta = { gen_index: 0, best: 0.85 };
    const result = autoMerge(current, delta) as unknown[];
    expect(result).toHaveLength(1);
  });

  it("replaces when delta is an array (full snapshot from server)", () => {
    const current = [{ gen_index: 0 }];
    const delta = [{ gen_index: 0 }, { gen_index: 1 }];
    expect(autoMerge(current, delta)).toBe(delta);
  });

  it("replaces when current state is a scalar object", () => {
    const current = { epoch: 1, loss: 0.5 };
    const delta = { epoch: 2, loss: 0.3 };
    expect(autoMerge(current, delta)).toBe(delta);
  });

  it("merges an iteration row into an IterationsResponse snapshot", () => {
    const current = {
      iterations: [{ iter_index: 0, phase: "reflect", score: 0.5 }],
      max_iter: 2,
      threshold: null,
      converged: false,
    };
    const result = autoMerge(current, {
      iter_index: 1,
      phase: "refine",
      score: null,
      text: "draft",
      metadata: {},
    }) as typeof current;

    expect(result.iterations).toHaveLength(2);
    expect(result.max_iter).toBe(2);
    expect(result.converged).toBe(false);
  });

  it("preserves multiple iteration phases while merging into a snapshot", () => {
    const current = {
      iterations: [{ iter_index: 1, phase: "refine", score: null }],
      max_iter: 2,
      threshold: null,
      converged: false,
    };
    const result = autoMerge(current, {
      iter_index: 1,
      phase: "reflect",
      score: 1,
      text: "accepted",
      metadata: {},
    }) as typeof current;

    expect(result.iterations.map((row) => row.phase)).toEqual(["refine", "reflect"]);
  });

  it("does not let SSE history replay replace the snapshot object", () => {
    const current = {
      iterations: [{ iter_index: 0, phase: "reflect", score: 1 }],
      max_iter: 2,
      threshold: null,
      converged: false,
    };
    const result = autoMerge(current, {
      iter_index: 0,
      phase: "reflect",
      score: 1,
      text: "same event",
      metadata: {},
    });

    expect(result).toEqual(current);
  });

  it("replaces when current is undefined (first delta before JSON resolves)", () => {
    expect(autoMerge(undefined, { epoch: 1 })).toEqual({ epoch: 1 });
  });

  it("replaces null current", () => {
    expect(autoMerge(null, { epoch: 1 })).toEqual({ epoch: 1 });
  });
});
