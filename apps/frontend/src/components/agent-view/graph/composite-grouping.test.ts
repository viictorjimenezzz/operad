import {
  applyCompositeCollapse,
  deriveCompositeGroups,
  toggleComposite,
} from "@/components/agent-view/graph/composite-grouping";
import { describe, expect, it } from "vitest";

// Legacy-shape io_graph (empty `composites` field) — exercises the fallback path
// where the backend predates the composites array and we synthesize from
// edge composite_path metadata.
const legacyIoGraph = {
  root: "Pipeline",
  nodes: [
    { key: "A", name: "A", fields: [] },
    { key: "B", name: "B", fields: [] },
    { key: "C", name: "C", fields: [] },
    { key: "D", name: "D", fields: [] },
  ],
  edges: [
    {
      agent_path: "Pipeline.inner.step_0",
      class_name: "First",
      kind: "leaf",
      from: "A",
      to: "B",
      composite_path: "Pipeline.inner",
    },
    {
      agent_path: "Pipeline.inner.step_1",
      class_name: "Second",
      kind: "leaf",
      from: "B",
      to: "C",
      composite_path: "Pipeline.inner",
    },
    {
      agent_path: "Pipeline.final",
      class_name: "Final",
      kind: "leaf",
      from: "C",
      to: "D",
      composite_path: null,
    },
  ],
  composites: [],
};

// New-shape io_graph with hierarchical composites (Sequential containing
// Sequential containing two leaves, plus a sibling leaf).
const nestedIoGraph = {
  root: "Outer",
  nodes: [
    { key: "A", name: "A", fields: [] },
    { key: "B", name: "B", fields: [] },
    { key: "C", name: "C", fields: [] },
    { key: "D", name: "D", fields: [] },
  ],
  edges: [
    {
      agent_path: "Outer.inner.step_0",
      class_name: "First",
      kind: "leaf",
      from: "A",
      to: "B",
      composite_path: "Outer.inner",
    },
    {
      agent_path: "Outer.inner.step_1",
      class_name: "Second",
      kind: "leaf",
      from: "B",
      to: "C",
      composite_path: "Outer.inner",
    },
    {
      agent_path: "Outer.tail",
      class_name: "Tail",
      kind: "leaf",
      from: "C",
      to: "D",
      composite_path: null,
    },
  ],
  composites: [
    {
      path: "Outer.inner",
      class_name: "InnerSequential",
      kind: "composite" as const,
      parent_path: null,
      children: ["Outer.inner.step_0", "Outer.inner.step_1"],
    },
  ],
};

describe("composite grouping (legacy fallback)", () => {
  it("derives composite groups from edge composite_path", () => {
    const groups = deriveCompositeGroups(legacyIoGraph);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.path).toBe("Pipeline.inner");
    expect(groups[0]?.collapsed).toBe(true);
  });

  it("replaces collapsed members with a super-edge", () => {
    const groups = deriveCompositeGroups(legacyIoGraph);
    const collapsed = applyCompositeCollapse(legacyIoGraph, groups);
    expect(collapsed.edges.some((e) => e.agent_path === "Pipeline.inner.__collapsed__")).toBe(true);
    expect(collapsed.edges.some((e) => e.agent_path === "Pipeline.inner.step_0")).toBe(false);
    expect(collapsed.edges.some((e) => e.agent_path === "Pipeline.final")).toBe(true);
  });

  it("keeps original members when expanded", () => {
    const groups = deriveCompositeGroups(legacyIoGraph).map((g) => ({ ...g, collapsed: false }));
    const expanded = applyCompositeCollapse(legacyIoGraph, groups);
    expect(expanded.edges.some((e) => e.agent_path === "Pipeline.inner.__collapsed__")).toBe(false);
    expect(expanded.edges.some((e) => e.agent_path === "Pipeline.inner.step_0")).toBe(true);
    expect(expanded.edges.some((e) => e.agent_path === "Pipeline.inner.step_1")).toBe(true);
  });
});

describe("composite grouping (composites array)", () => {
  it("uses composites array when present and includes className from backend", () => {
    const groups = deriveCompositeGroups(nestedIoGraph);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.path).toBe("Outer.inner");
    expect(groups[0]?.className).toBe("InnerSequential");
    expect(groups[0]?.parentPath).toBeNull();
    expect(groups[0]?.leafPaths).toEqual(["Outer.inner.step_0", "Outer.inner.step_1"]);
  });

  it("toggles a single composite by path", () => {
    const groups = deriveCompositeGroups(nestedIoGraph);
    const toggled = toggleComposite(groups, "Outer.inner");
    expect(toggled[0]?.collapsed).toBe(false);
  });

  it("hides leaves under a collapsed ancestor and shows the super-edge", () => {
    const groups = deriveCompositeGroups(nestedIoGraph);
    const result = applyCompositeCollapse(nestedIoGraph, groups);
    const paths = result.edges.map((e) => e.agent_path);
    expect(paths).toContain("Outer.inner.__collapsed__");
    expect(paths).toContain("Outer.tail"); // sibling leaf, no ancestor collapsed
    expect(paths).not.toContain("Outer.inner.step_0");
    expect(paths).not.toContain("Outer.inner.step_1");
  });
});
