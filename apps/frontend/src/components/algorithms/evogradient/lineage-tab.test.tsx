import { buildFocusedLineageGraph } from "@/components/algorithms/evogradient/evo-lineage-tab";
import type { EvoGeneration, EvoIndividual } from "@/components/algorithms/evogradient/evo-detail-overview";
import { describe, expect, it } from "vitest";

describe("buildFocusedLineageGraph", () => {
  it("shows selected lineages and collapses discarded siblings by default", () => {
    const generations: EvoGeneration[] = [
      generation(0, [
        individual(0, "l0", null, 0.8, true),
        individual(1, "l1", null, 0.4, false),
        individual(2, "l2", null, 0.3, false),
      ]),
      generation(1, [
        individual(0, "l0", null, 0.82, true),
        individual(1, "l3", "l0", 0.91, true),
        individual(2, "l4", "l0", 0.2, false),
      ]),
    ];

    const graph = buildFocusedLineageGraph(generations);

    expect(graph.nodes.filter((node) => node.kind === "individual")).toHaveLength(3);
    expect(graph.nodes.filter((node) => node.kind === "discarded")).toHaveLength(2);
    expect(graph.nodes.some((node) => node.id === "discarded-1-l0")).toBe(true);
    expect(graph.edges.some((edge) => edge.target === "discarded-1-l0")).toBe(true);
  });

  it("expands discarded candidates for a selected group", () => {
    const generations: EvoGeneration[] = [
      generation(0, [individual(0, "l0", null, 0.8, true)]),
      generation(1, [
        individual(0, "l0", null, 0.82, true),
        individual(1, "l1", "l0", 0.2, false),
      ]),
    ];

    const graph = buildFocusedLineageGraph(generations, new Set(["discarded-1-l0"]));

    expect(graph.nodes.some((node) => node.id === "discarded-1-l0")).toBe(false);
    expect(graph.nodes.some((node) => node.lineageId === "l1")).toBe(true);
  });
});

function generation(genIndex: number, individuals: EvoIndividual[]): EvoGeneration {
  const scores = individuals.map((item) => item.score ?? 0);
  const selected = individuals.filter((item) => item.selected).map((item) => item.individualId);
  return {
    genIndex,
    scores,
    best: Math.max(...scores),
    mean: scores.reduce((sum, score) => sum + score, 0) / scores.length,
    worst: Math.min(...scores),
    survivorIndices: selected,
    selectedLineageId: individuals.find((item) => item.selected)?.lineageId ?? null,
    individuals,
    mutations: individuals.map((item) => ({
      individualId: item.individualId,
      lineageId: item.lineageId,
      op: item.op,
      path: item.path,
      improved: item.improved,
    })),
    opAttempts: {},
    opSuccess: {},
    timestamp: null,
  };
}

function individual(
  individualId: number,
  lineageId: string,
  parentLineageId: string | null,
  score: number,
  selected: boolean,
): EvoIndividual {
  return {
    individualId,
    lineageId,
    parentLineageId,
    score,
    selected,
    op: "append_rule",
    path: "rules",
    improved: selected,
    parameterDeltas: [],
  };
}
