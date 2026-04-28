import { StructureTree } from "@/components/agent-view/structure/structure-tree";
import { buildStructureTree } from "@/lib/structure-tree";
import type { AgentGraphResponse, AgentParametersResponse } from "@/lib/types";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

const graph: AgentGraphResponse = {
  root: "research_analyst",
  nodes: [
    node("research_analyst", "ResearchAnalyst", "composite", null),
    node("research_analyst.planner", "Planner", "leaf", "research_analyst"),
    node("research_analyst.biology", "Parallel", "composite", "research_analyst"),
    node("research_analyst.biology.reason", "Reasoner", "leaf", "research_analyst.biology"),
    node("research_analyst.biology.loop", "Sequential", "composite", "research_analyst.biology"),
    node("research_analyst.biology.loop.actor", "Actor", "leaf", "research_analyst.biology.loop"),
    node(
      "research_analyst.biology.loop.extractor",
      "Extractor",
      "leaf",
      "research_analyst.biology.loop",
    ),
    node("research_analyst.writer", "Reasoner", "leaf", "research_analyst"),
  ],
  edges: [],
};

const params: AgentParametersResponse[] = [
  {
    agent_path: "research_analyst.biology.loop.actor",
    parameters: [
      {
        path: "role",
        type: "TextParameter",
        value: "Act on the plan.",
        requires_grad: true,
        grad: null,
        constraint: null,
      },
      {
        path: "config",
        type: "Configuration",
        value: { sampling: { temperature: 0.4 }, model: "mini" },
        requires_grad: false,
        grad: null,
        constraint: null,
      },
    ],
  },
];

describe("buildStructureTree", () => {
  it("builds the nested structural tree and leaf parameters", () => {
    const root = buildStructureTree(graph, params);

    expect(root.path).toBe("research_analyst");
    expect(root.kind).toBe("composite");
    expect(root.children.map((child) => child.label)).toEqual(["planner", "biology", "writer"]);
    expect(root.children[1]?.children.map((child) => child.label)).toEqual(["reason", "loop"]);
    expect(root.children[1]?.children[1]?.children.map((child) => child.className)).toEqual([
      "Actor",
      "Extractor",
    ]);

    const actor = root.children[1]?.children[1]?.children[0];
    expect(actor?.parameters.map((param) => param.path)).toEqual([
      "role",
      "task",
      "rules",
      "examples",
      "config.sampling.temperature",
      "config.model",
    ]);
    expect(actor?.parameters.find((param) => param.path === "role")?.requiresGrad).toBe(true);
    expect(
      actor?.parameters.find((param) => param.path === "config.sampling.temperature")?.type,
    ).toBe("float");
    expect(actor?.parameters.find((param) => param.path === "config.model")?.type).toBe(
      "categorical",
    );
  });

  it("leaves composites with more than five children collapsed by default", () => {
    const wideGraph: AgentGraphResponse = {
      root: "Root",
      nodes: [
        node("Root", "Root", "composite", null),
        ...Array.from({ length: 6 }, (_, index) =>
          node(`Root.leaf_${index}`, "Leaf", "leaf", "Root"),
        ),
      ],
      edges: [],
    };
    const root = buildStructureTree(wideGraph, []);

    render(<StructureTree root={root} />);

    expect(screen.queryByText("leaf_0")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "expand composite" }));
    expect(screen.getByText("leaf_0")).toBeTruthy();
  });
});

describe("StructureTree", () => {
  it("renders trainable leaf state and selects trainable parameters", () => {
    const onSelectParameter = vi.fn();
    const root = buildStructureTree(graph, params);

    render(<StructureTree root={root} onSelectParameter={onSelectParameter} />);

    fireEvent.click(screen.getByRole("button", { name: /Actor actor/ }));
    expect(screen.getByLabelText("trainable parameters")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /role Act on the plan/ }));
    expect(onSelectParameter).toHaveBeenCalledWith(
      expect.objectContaining({ fullPath: "research_analyst.biology.loop.actor.role" }),
      expect.objectContaining({ path: "research_analyst.biology.loop.actor" }),
    );
  });

  it("supports keyboard navigation and selection", () => {
    const onSelectAgent = vi.fn();
    const root = buildStructureTree(graph, params);

    render(<StructureTree root={root} onSelectAgent={onSelectAgent} />);
    const tree = screen.getByRole("tree", { name: "agent structure" });

    tree.focus();
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    fireEvent.keyDown(tree, { key: "Enter" });

    expect(onSelectAgent).toHaveBeenCalledWith(
      expect.objectContaining({ path: "research_analyst.planner" }),
    );
  });

  it("expands collapsed rows from the keyboard", () => {
    const root = buildStructureTree(graph, params);

    render(<StructureTree root={root} />);
    const tree = screen.getByRole("tree", { name: "agent structure" });

    tree.focus();
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    fireEvent.keyDown(tree, { key: "ArrowDown" });
    fireEvent.keyDown(tree, { key: "ArrowRight" });

    expect(screen.getByRole("button", { name: /role Act on the plan/ })).toBeTruthy();
  });
});

function node(
  path: string,
  class_name: string,
  kind: "leaf" | "composite",
  parent_path: string | null,
) {
  return {
    path,
    class_name,
    kind,
    parent_path,
    input: "Input",
    output: "Output",
    input_label: "Input",
    output_label: "Output",
  };
}
