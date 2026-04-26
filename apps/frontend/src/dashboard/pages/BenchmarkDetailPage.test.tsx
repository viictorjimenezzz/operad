import { describe, expect, it } from "vitest";

import { toScatterPoints } from "./BenchmarkDetailPage";

describe("toScatterPoints", () => {
  it("preserves one point per cell and computes token cost", () => {
    const points = toScatterPoints([
      {
        task: "classification",
        method: "tgd",
        seed: 0,
        metric: "accuracy",
        score: 0.8,
        tokens: { prompt: 100, completion: 25 },
        latency_s: 1.2,
      },
      {
        task: "summarization",
        method: "momentum",
        seed: 1,
        metric: "rouge",
        score: 0.6,
        tokens: { prompt: 80, completion: 10 },
        latency_s: 1.0,
      },
    ]);

    expect(points).toHaveLength(2);
    expect(points[0]?.cost).toBe(125);
    expect(points[1]?.cost).toBe(90);
  });
});
