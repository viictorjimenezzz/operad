import { buildLineageGraph } from "@/components/algorithms/evogradient/lineage-tab";
import type { EvoGeneration } from "@/components/algorithms/evogradient/evo-detail-overview";
import { describe, expect, it } from "vitest";

describe("buildLineageGraph", () => {
  it("builds one node per individual and one parent edge per non-initial generation individual", () => {
    const generations: EvoGeneration[] = [
      generation(0, [0.1, 0.2, 0.3, 0.4, 0.5], [4, 3]),
      generation(1, [0.2, 0.21, 0.31, 0.45, 0.52], [4, 2]),
      generation(2, [0.25, 0.27, 0.33, 0.47, 0.6], [4, 3]),
    ];

    const graph = buildLineageGraph(generations);

    expect(graph.nodes).toHaveLength(15);
    expect(graph.edges).toHaveLength(10);
  });
});

function generation(genIndex: number, scores: number[], survivorIndices: number[]): EvoGeneration {
  return {
    genIndex,
    scores,
    best: Math.max(...scores),
    mean: scores.reduce((sum, score) => sum + score, 0) / scores.length,
    worst: Math.min(...scores),
    survivorIndices,
    mutations: scores.map((_, individualId) => ({
      individualId,
      op: "mutate",
      path: "role",
      improved: true,
    })),
    opAttempts: {},
    opSuccess: {},
    timestamp: null,
  };
}
