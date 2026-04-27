import {
  type ScenarioTreeInfo,
  type TalkerTurn,
  currentNodeId,
  extractScenarioTree,
  extractTalkerTurns,
  walkedPathFromTurns,
} from "@/components/algorithms/talker_reasoner/transcript-view";
import { EmptyState, Pill } from "@/components/ui";
import dagre from "@dagrejs/dagre";
import {
  Background,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

interface ScenarioTreeViewProps {
  tree: ScenarioTreeInfo;
  walkedPath: string[];
  currentNodeId: string | null;
  onNodeSelect?: (nodeId: string) => void;
  selectedNodeId?: string | null;
  turns?: TalkerTurn[];
  live?: boolean;
}

interface TalkerTreeTabProps {
  summary?: unknown;
  events?: unknown;
}

interface ScenarioNodeData extends Record<string, unknown> {
  title: string;
  prompt: string;
  terminal: boolean;
  walked: boolean;
  current: boolean;
  selected: boolean;
  turnCount: number;
  live: boolean;
  onSelect: () => void;
}

const nodeTypes = { scenario: ScenarioNodeCard };

export function TalkerTreeTab({ summary, events }: TalkerTreeTabProps) {
  const tree = extractScenarioTree(events);
  const turns = extractTalkerTurns(summary, events);
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedNodeId = searchParams.get("node");
  const live =
    (summary && typeof summary === "object" ? (summary as Record<string, unknown>).state : null) ===
    "running";

  if (!tree) {
    return (
      <EmptyState
        title="tree payload missing — re-run with the latest TalkerReasoner"
        description="the algo_start event does not include the ScenarioTree payload required for this tab"
      />
    );
  }

  return (
    <ScenarioTreeView
      tree={tree}
      walkedPath={walkedPathFromTurns(tree, turns)}
      currentNodeId={currentNodeId(summary, tree, turns)}
      selectedNodeId={selectedNodeId}
      turns={turns}
      live={live}
      onNodeSelect={(nodeId) =>
        setSearchParams(
          (current) => {
            const next = new URLSearchParams(current);
            next.set("node", nodeId);
            return next;
          },
          { replace: true },
        )
      }
    />
  );
}

export function ScenarioTreeView({
  tree,
  walkedPath,
  currentNodeId: activeNodeId,
  onNodeSelect,
  selectedNodeId,
  turns = [],
  live = false,
}: ScenarioTreeViewProps) {
  return (
    <ReactFlowProvider>
      <ScenarioTreeCanvas
        tree={tree}
        walkedPath={walkedPath}
        currentNodeId={activeNodeId}
        selectedNodeId={selectedNodeId ?? null}
        turns={turns}
        live={live}
        onNodeSelect={onNodeSelect}
      />
    </ReactFlowProvider>
  );
}

function ScenarioTreeCanvas({
  tree,
  walkedPath,
  currentNodeId: activeNodeId,
  selectedNodeId,
  turns,
  live,
  onNodeSelect,
}: Required<Pick<ScenarioTreeViewProps, "tree" | "walkedPath" | "turns" | "live">> & {
  currentNodeId: string | null;
  selectedNodeId: string | null;
  onNodeSelect: ((nodeId: string) => void) | undefined;
}) {
  const { fitView } = useReactFlow();
  const [, setSearchParams] = useSearchParams();
  const turnCounts = useMemo(() => countTurnsByNode(turns), [turns]);
  const walkedEdges = useMemo(() => {
    const out = new Set<string>();
    for (let i = 1; i < walkedPath.length; i += 1) {
      out.add(`${walkedPath[i - 1]}->${walkedPath[i]}`);
    }
    return out;
  }, [walkedPath]);

  const { nodes, edges } = useMemo(() => {
    const graphNodes: Node<ScenarioNodeData>[] = tree.nodes.map((node) => ({
      id: node.id,
      type: "scenario",
      position: { x: 0, y: 0 },
      data: {
        title: node.title,
        prompt: node.prompt,
        terminal: node.terminal,
        walked: walkedPath.includes(node.id),
        current: activeNodeId === node.id,
        selected: selectedNodeId === node.id,
        turnCount: turnCounts.get(node.id) ?? 0,
        live,
        onSelect: () => onNodeSelect?.(node.id),
      },
    }));
    const graphEdges: Edge[] = tree.nodes.flatMap((node) => {
      if (!node.parent_id) return [];
      const walked = walkedEdges.has(`${node.parent_id}->${node.id}`);
      return [
        {
          id: `${node.parent_id}->${node.id}`,
          source: node.parent_id,
          target: node.id,
          markerEnd: { type: MarkerType.ArrowClosed },
          style: {
            stroke: walked ? "var(--qual-7)" : "var(--color-border-strong)",
            strokeWidth: walked ? 3 : 1.2,
            opacity: walked ? 0.95 : 0.45,
          },
        },
      ];
    });
    return { nodes: layout(graphNodes, graphEdges), edges: graphEdges };
  }, [tree, walkedPath, activeNodeId, selectedNodeId, turnCounts, live, onNodeSelect, walkedEdges]);

  const fitTrigger = `${nodes.length}:${edges.length}`;
  useEffect(() => {
    void fitTrigger;
    const id = window.setTimeout(() => fitView({ padding: 0.2, duration: 180 }), 120);
    return () => window.clearTimeout(id);
  }, [fitView, fitTrigger]);

  const selectedNode = selectedNodeId
    ? (tree.nodes.find((node) => node.id === selectedNodeId) ?? null)
    : null;
  const selectedTurns = selectedNodeId
    ? turns.filter((turn) => turn.fromNodeId === selectedNodeId || turn.toNodeId === selectedNodeId)
    : [];

  return (
    <div className="grid h-full min-h-[640px] grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_280px]">
      <div className="overflow-hidden rounded-lg border border-border bg-bg-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          maxZoom={1.4}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={24} />
          {tree.nodes.length > 15 ? (
            <MiniMap
              nodeStrokeWidth={2}
              pannable
              zoomable
              maskColor="rgba(0,0,0,0.25)"
              style={{ background: "var(--color-bg-2)" }}
            />
          ) : null}
          <Controls showInteractive={false} className="!border-border !bg-bg-1 !text-text" />
        </ReactFlow>
      </div>

      <aside className="min-h-0 overflow-auto rounded-lg border border-border bg-bg-1 p-3">
        {selectedNode ? (
          <div className="flex flex-col gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.08em] text-muted-2">node</div>
              <div className="mt-1 font-mono text-sm text-text">{selectedNode.id}</div>
              <div className="mt-1 text-[12px] text-muted">{selectedNode.title}</div>
            </div>
            <div className="rounded border border-border bg-bg-2 p-2 text-[12px] text-muted">
              {selectedNode.prompt || "no prompt recorded"}
            </div>
            <div>
              <div className="mb-2 text-[10px] uppercase tracking-[0.08em] text-muted-2">
                visited
              </div>
              {selectedTurns.length > 0 ? (
                <div className="flex flex-col gap-2">
                  {selectedTurns.map((turn) => (
                    <button
                      key={turn.turnIndex}
                      type="button"
                      onClick={() =>
                        setSearchParams(
                          (current) => {
                            const next = new URLSearchParams(current);
                            next.set("tab", "transcript");
                            next.set("turn", String(turn.turnIndex + 1));
                            return next;
                          },
                          { replace: false },
                        )
                      }
                      className="rounded border border-border bg-bg-2 px-2 py-1.5 text-left text-[12px] transition-colors hover:border-border-strong"
                    >
                      <span className="font-mono text-text">turn {turn.turnIndex + 1}</span>
                      <span className="ml-2 text-muted">{turn.decisionKind}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-[12px] text-muted">no turns spent at this node</div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full min-h-48 items-center justify-center text-center text-[12px] text-muted">
            Select a scenario node to inspect turns spent there.
          </div>
        )}
      </aside>
    </div>
  );
}

function ScenarioNodeCard({ data }: NodeProps) {
  const node = data as ScenarioNodeData;
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        node.onSelect();
      }}
      className="nodrag nopan w-[190px] rounded-md border bg-bg-2 p-2 text-left shadow-[var(--shadow-card-soft)] transition-colors hover:border-border-strong"
      style={{
        borderColor: node.selected
          ? "var(--color-accent)"
          : node.walked
            ? "var(--qual-7)"
            : "var(--color-border)",
      }}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-muted-2" />
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[12px] font-medium text-text">{node.title}</div>
          <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-muted">{node.prompt}</div>
        </div>
        {node.current ? (
          <span className="relative mt-1 inline-flex h-2 w-2 shrink-0">
            {node.live ? (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[--color-live] opacity-70" />
            ) : null}
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[--color-live]" />
          </span>
        ) : null}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        {node.terminal ? <Pill tone="warn">terminal</Pill> : <span />}
        {node.turnCount > 0 ? (
          <span className="rounded bg-bg-3 px-1.5 py-0.5 font-mono text-[10px] text-muted">
            {node.turnCount} turns
          </span>
        ) : null}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0 !bg-muted-2"
      />
    </button>
  );
}

function countTurnsByNode(turns: TalkerTurn[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const turn of turns) {
    const node = turn.fromNodeId || turn.toNodeId;
    if (!node) continue;
    counts.set(node, (counts.get(node) ?? 0) + 1);
  }
  return counts;
}

function layout(nodes: Node<ScenarioNodeData>[], edges: Edge[]): Node<ScenarioNodeData>[] {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "TB", nodesep: 34, ranksep: 76, marginx: 40, marginy: 40 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) graph.setNode(node.id, { width: 190, height: 100 });
  for (const edge of edges) graph.setEdge(edge.source, edge.target);
  dagre.layout(graph);
  return nodes.map((node) => {
    const point = graph.node(node.id);
    if (!point) return node;
    return {
      ...node,
      position: { x: point.x - 95, y: point.y - 50 },
    };
  });
}
