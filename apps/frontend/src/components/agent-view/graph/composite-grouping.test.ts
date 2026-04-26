import {
  applyCompositeCollapse,
  deriveCompositeGroups,
} from "@/components/agent-view/graph/composite-grouping";
import { describe, expect, it } from "vitest";

const ioGraph = {
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
};

describe("composite grouping", () => {
  it("derives composite groups from edge composite_path", () => {
    const groups = deriveCompositeGroups(ioGraph);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.path).toBe("Pipeline.inner");
    expect(groups[0]?.collapsed).toBe(true);
  });

  it("replaces collapsed members with a super-edge", () => {
    const groups = deriveCompositeGroups(ioGraph);
    const collapsed = applyCompositeCollapse(ioGraph, groups);
    expect(collapsed.edges.some((e) => e.agent_path === "Pipeline.inner.__collapsed__")).toBe(true);
    expect(collapsed.edges.some((e) => e.agent_path === "Pipeline.inner.step_0")).toBe(false);
    expect(collapsed.edges.some((e) => e.agent_path === "Pipeline.final")).toBe(true);
  });

  it("keeps original members when expanded", () => {
    const groups = deriveCompositeGroups(ioGraph).map((g) => ({ ...g, collapsed: false }));
    const expanded = applyCompositeCollapse(ioGraph, groups);
    expect(expanded.edges.some((e) => e.agent_path === "Pipeline.inner.__collapsed__")).toBe(false);
    expect(expanded.edges.some((e) => e.agent_path === "Pipeline.inner.step_0")).toBe(true);
    expect(expanded.edges.some((e) => e.agent_path === "Pipeline.inner.step_1")).toBe(true);
  });
});
