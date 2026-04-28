import { AgentFlowGraph } from "@/components/agent-view/graph/agent-flow-graph";
import { layoutAgentFlow } from "@/components/agent-view/graph/agent-flow-layout";
import type { AgentGraphResponse } from "@/lib/types";
import { useUIStore } from "@/stores";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@xyflow/react", () => ({
  ReactFlowProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  ReactFlow: ({
    defaultNodes,
    nodes,
    onNodeClick,
  }: {
    defaultNodes?: Array<{ id: string; type?: string; data: unknown }>;
    nodes?: Array<{ id: string; type?: string; data: unknown }>;
    onNodeClick?: (e: unknown, node: { id: string; type?: string }) => void;
  }) => {
    const list = defaultNodes ?? nodes ?? [];
    return (
      <div>
        {list.map((node) => (
          <button
            key={node.id}
            type="button"
            onClick={(e) => onNodeClick?.(e, node)}
          >
            {node.id}
          </button>
        ))}
      </div>
    );
  },
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
  Handle: () => null,
  BaseEdge: () => null,
  EdgeLabelRenderer: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Position: { Left: "left", Right: "right" },
  getBezierPath: () => ["", 0, 0],
  useReactFlow: () => ({ fitView: vi.fn() }),
}));

vi.mock("@/components/agent-view/graph/use-active-agents", () => ({
  useActiveAgents: () => new Set<string>(),
}));

vi.mock("@/lib/api/dashboard", () => ({
  dashboardApi: {
    agentInvocations: vi.fn(async () => ({ agent_path: "Root.leaf", invocations: [] })),
    agentMeta: vi.fn(async () => ({
      agent_path: "Root.leaf",
      class_name: "Leaf",
      kind: "leaf",
      hash_content: "hash",
      role: null,
      task: null,
      rules: [],
      examples: [],
      config: null,
      input_schema: null,
      output_schema: null,
      forward_in_overridden: false,
      forward_out_overridden: false,
      trainable_paths: [],
      langfuse_search_url: null,
    })),
    graph: vi.fn(async () => ({ mermaid: "graph TD" })),
  },
}));

const nestedAgentGraph: AgentGraphResponse = {
  root: "Research",
  nodes: [
    {
      path: "Research",
      class_name: "Research",
      kind: "composite",
      parent_path: null,
      input: "Question",
      output: "Answer",
      input_label: "Question",
      output_label: "Answer",
    },
    {
      path: "Research.stage_0",
      class_name: "Planner",
      kind: "leaf",
      parent_path: "Research",
      input: "Question",
      output: "Plan",
      input_label: "Question",
      output_label: "Plan",
    },
    {
      path: "Research.stage_1",
      class_name: "Parallel",
      kind: "composite",
      parent_path: "Research",
      input: "Plan",
      output: "Findings",
      input_label: "Plan",
      output_label: "Findings",
    },
    {
      path: "Research.stage_1.biology",
      class_name: "Biology",
      kind: "leaf",
      parent_path: "Research.stage_1",
      input: "Plan",
      output: "BiologyFinding",
      input_label: "Plan",
      output_label: "BiologyFinding",
    },
    {
      path: "Research.stage_1.chemistry",
      class_name: "Chemistry",
      kind: "leaf",
      parent_path: "Research.stage_1",
      input: "Plan",
      output: "ChemistryFinding",
      input_label: "Plan",
      output_label: "ChemistryFinding",
    },
    {
      path: "Research.stage_2",
      class_name: "Writer",
      kind: "leaf",
      parent_path: "Research",
      input: "Findings",
      output: "Answer",
      input_label: "Findings",
      output_label: "Answer",
    },
  ],
  edges: [
    { caller: "Research.stage_0", callee: "Research.stage_1", type: "call", input: "", output: "" },
    {
      caller: "Research.stage_1",
      callee: "Research.stage_1.biology",
      type: "call",
      input: "",
      output: "",
    },
    {
      caller: "Research.stage_1",
      callee: "Research.stage_1.chemistry",
      type: "call",
      input: "",
      output: "",
    },
    {
      caller: "Research.stage_1.biology",
      callee: "Research.stage_2",
      type: "call",
      input: "",
      output: "",
    },
    {
      caller: "Research.stage_1.chemistry",
      callee: "Research.stage_2",
      type: "call",
      input: "",
      output: "",
    },
  ],
};

function wrapper(children: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("layoutAgentFlow", () => {
  it("lays out all-expanded nested composites without rendering containment edges", () => {
    const result = layoutAgentFlow({
      nodes: nestedAgentGraph.nodes,
      edges: nestedAgentGraph.edges,
      rootPath: nestedAgentGraph.root,
      expanded: new Set(["Research.stage_1"]),
    });

    expect(result.nodes.filter((node) => !node.hidden).map((node) => node.path)).toContain(
      "Research.stage_1.biology",
    );
    expect(result.edges.some((edge) => edge.visible && edge.caller === "Research.stage_1")).toBe(
      false,
    );
  });
});

describe("AgentFlowGraph selection", () => {
  beforeEach(() => {
    useUIStore.getState().clearGraphSelection();
  });

  it("selects leaves as inspector agent edges", () => {
    const graph: AgentGraphResponse = {
      root: "Root",
      nodes: [
        {
          path: "Root",
          class_name: "Root",
          kind: "composite",
          parent_path: null,
          input: "In",
          output: "Out",
          input_label: "In",
          output_label: "Out",
        },
        {
          path: "Root.leaf",
          class_name: "Leaf",
          kind: "leaf",
          parent_path: "Root",
          input: "In",
          output: "Out",
          input_label: "In",
          output_label: "Out",
        },
      ],
      edges: [],
    };

    render(wrapper(<AgentFlowGraph agentGraph={graph} runId="run-1" />));
    fireEvent.click(screen.getByRole("button", { name: "Root.leaf" }));

    expect(useUIStore.getState().graphSelection).toEqual({
      kind: "edge",
      agentPath: "Root.leaf",
    });
  });
});
