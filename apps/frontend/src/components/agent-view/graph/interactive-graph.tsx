import { AgentEdge } from "@/components/agent-view/graph/agent-edge";
import {
  type CompositeGroup,
  applyCompositeCollapse,
  deriveCompositeGroups,
} from "@/components/agent-view/graph/composite-grouping";
import { IoTypeNode } from "@/components/agent-view/graph/io-type-node";
import { applyDagreLayout } from "@/components/agent-view/graph/layout";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { IoGraphResponse } from "@/lib/types";
import { useUIStore } from "@/stores/ui";
import {
  Background,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo, useState } from "react";

interface InteractiveGraphProps {
  ioGraph: IoGraphResponse | null | undefined;
  runId: string;
}

const nodeTypes = { ioType: IoTypeNode };
const edgeTypes = { agentEdge: AgentEdge };

function GraphCanvas({ ioGraph, runId }: InteractiveGraphProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const selectedInvocationAgentPath = useUIStore((s) => s.selectedInvocationAgentPath);
  const [groups, setGroups] = useState<CompositeGroup[]>(() =>
    deriveCompositeGroups(ioGraph ?? { root: null, nodes: [], edges: [] }),
  );

  const source = useMemo(() => {
    const graph = ioGraph ?? { root: null, nodes: [], edges: [] };
    if (groups.length === 0) return graph;
    return applyCompositeCollapse(graph, groups);
  }, [groups, ioGraph]);

  const withGroups = useMemo(() => {
    if (!ioGraph) return [] as CompositeGroup[];
    return deriveCompositeGroups(ioGraph);
  }, [ioGraph]);

  const nodes: Node[] = useMemo(() => {
    const activeEdgePath = selectedEdgeId ?? selectedInvocationAgentPath;
    const graphNodes = source.nodes.map((node) => {
      const incidentEdge = source.edges.find(
        (edge) => edge.from === node.key || edge.to === node.key,
      );
      const selected = selectedNodeId === node.key;
      const dimmed = activeEdgePath
        ? !source.edges.some(
            (edge) =>
              edge.agent_path === activeEdgePath &&
              (edge.from === node.key || edge.to === node.key),
          )
        : false;

      return {
        id: node.key,
        type: "ioType",
        position: { x: 0, y: 0 },
        data: {
          label: node.name,
          fields: node.fields,
          agentPath: incidentEdge?.agent_path ?? source.root ?? "root",
          selected,
          dimmed,
          onSelect: () => {
            setSelectedEdgeId(null);
            setSelectedNodeId((curr) => (curr === node.key ? null : node.key));
          },
          onClose: () => setSelectedNodeId(null),
        },
        ariaLabel: `type node ${node.name}`,
      } satisfies Node;
    });

    const graphEdges: Edge[] = source.edges.map((edge) => {
      const selected = activeEdgePath === edge.agent_path;
      const dimmed = Boolean(activeEdgePath && activeEdgePath !== edge.agent_path);
      return {
        id: edge.agent_path,
        source: edge.from,
        target: edge.to,
        type: "agentEdge",
        data: {
          runId,
          agentPath: edge.agent_path,
          label: edge.class_name,
          selected,
          dimmed,
          onSelect: () => {
            setSelectedNodeId(null);
            setSelectedEdgeId((curr) => (curr === edge.agent_path ? null : edge.agent_path));
          },
          onClose: () => setSelectedEdgeId(null),
        },
        ariaLabel: `agent edge ${edge.class_name}`,
      } satisfies Edge;
    });

    return applyDagreLayout(graphNodes, graphEdges);
  }, [source, selectedEdgeId, selectedInvocationAgentPath, selectedNodeId, runId]);

  const edges: Edge[] = useMemo(() => {
    const activeEdgePath = selectedEdgeId ?? selectedInvocationAgentPath;
    return source.edges.map((edge) => ({
      id: edge.agent_path,
      source: edge.from,
      target: edge.to,
      type: "agentEdge",
      data: {
        runId,
        agentPath: edge.agent_path,
        label: edge.class_name,
        selected: activeEdgePath === edge.agent_path,
        dimmed: Boolean(activeEdgePath && activeEdgePath !== edge.agent_path),
        onSelect: () => {
          setSelectedNodeId(null);
          setSelectedEdgeId((curr) => (curr === edge.agent_path ? null : edge.agent_path));
        },
        onClose: () => setSelectedEdgeId(null),
      },
    }));
  }, [source, runId, selectedEdgeId, selectedInvocationAgentPath]);

  return (
    <div className="h-[520px] overflow-hidden rounded border border-border">
      <div className="flex flex-wrap items-center gap-1 border-b border-border bg-bg-2 px-2 py-1 text-[11px]">
        {withGroups.length === 0 ? <span className="text-muted">no composite groups</span> : null}
        {withGroups.map((group) => {
          const state = groups.find((g) => g.path === group.path);
          const collapsed = state?.collapsed ?? true;
          return (
            <Button
              key={group.path}
              size="sm"
              variant="ghost"
              className="h-6 px-2 text-[11px]"
              onClick={() =>
                setGroups((curr) => {
                  const idx = curr.findIndex((g) => g.path === group.path);
                  if (idx < 0) return [...curr, { ...group, collapsed: false }];
                  const next = [...curr];
                  const entry = next[idx];
                  if (!entry) return curr;
                  next[idx] = { ...entry, collapsed: !entry.collapsed };
                  return next;
                })
              }
              title={group.path}
            >
              {collapsed ? "expand" : "collapse"} {group.className}
            </Button>
          );
        })}
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        panOnDrag
        zoomOnScroll
        minZoom={0.2}
        maxZoom={2}
        onPaneClick={() => {
          setSelectedNodeId(null);
          setSelectedEdgeId(null);
        }}
      >
        <Background color="var(--color-border)" gap={18} />
        <MiniMap
          pannable
          zoomable
          maskColor="rgba(7, 9, 16, 0.75)"
          nodeColor={() => "var(--color-bg-2)"}
          nodeStrokeColor={() => "var(--color-border)"}
          nodeStrokeWidth={1}
          style={{
            background: "var(--color-bg-1)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
          }}
        />
        <Controls showInteractive />
      </ReactFlow>
    </div>
  );
}

export function InteractiveGraph({ ioGraph, runId }: InteractiveGraphProps) {
  if (!ioGraph || ioGraph.edges.length === 0 || ioGraph.nodes.length === 0) {
    return <EmptyState title="waiting for first invocation" description="graph not ready yet" />;
  }
  return (
    <ReactFlowProvider>
      <GraphCanvas ioGraph={ioGraph} runId={runId} />
    </ReactFlowProvider>
  );
}
