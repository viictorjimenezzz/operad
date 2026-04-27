import {
  type EvoGeneration,
  type EvoMutation,
  buildEvoGenerations,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import { EmptyState } from "@/components/ui";
import dagre from "@dagrejs/dagre";
import {
  Background,
  Controls,
  type Edge,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

interface EvoLineageTabProps {
  summary?: unknown;
  fitness?: unknown;
  events?: unknown;
}

interface LineageNodeData extends Record<string, unknown> {
  generation: number;
  score: number | null;
  op: string;
  path: string;
  survivor: boolean;
  winner: boolean;
  onSelect: () => void;
}

const nodeTypes = { lineage: LineageNode };

export function EvoLineageTab({ summary, fitness, events }: EvoLineageTabProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  if (generations.length === 0) {
    return (
      <EmptyState
        title="no survivor lineage yet"
        description="lineage appears after EvoGradient emits generation survivor indices"
      />
    );
  }
  return (
    <ReactFlowProvider>
      <LineageCanvas generations={generations} />
    </ReactFlowProvider>
  );
}

function LineageCanvas({ generations }: { generations: EvoGeneration[] }) {
  const [, setSearchParams] = useSearchParams();
  const { fitView } = useReactFlow();
  const { nodes, edges } = useMemo(() => {
    const rawNodes: Node<LineageNodeData>[] = [];
    const rawEdges: Edge[] = [];
    let previousWinner: string | null = null;

    for (const generation of generations) {
      const winnerIndex = bestSurvivorIndex(generation);
      const survivorIndices =
        generation.survivorIndices.length > 0 ? generation.survivorIndices : [winnerIndex];

      for (const survivorIndex of survivorIndices) {
        const id = nodeId(generation.genIndex, survivorIndex);
        const mutation = mutationFor(generation, survivorIndex);
        const winner = survivorIndex === winnerIndex;
        rawNodes.push({
          id,
          type: "lineage",
          position: { x: 0, y: 0 },
          data: {
            generation: generation.genIndex,
            score: generation.scores[survivorIndex] ?? null,
            op: mutation?.op ?? "identity",
            path: mutation?.path ?? "",
            survivor: true,
            winner,
            onSelect: () =>
              setSearchParams(
                (current) => {
                  const next = new URLSearchParams(current);
                  next.set("tab", "best-diff");
                  next.set("gen", String(generation.genIndex));
                  return next;
                },
                { replace: false },
              ),
          },
        });

        if (previousWinner) {
          rawEdges.push({
            id: `${previousWinner}-${id}`,
            source: previousWinner,
            target: id,
            label: edgeLabel(mutation),
            animated: winner,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: {
              stroke: winner ? "var(--qual-7)" : "var(--color-border-strong)",
              strokeWidth: winner ? 2.5 : 1.2,
              opacity: winner ? 0.95 : 0.45,
            },
            labelStyle: { fill: "var(--color-muted)", fontSize: 10 },
          });
        }
      }
      previousWinner = nodeId(generation.genIndex, winnerIndex);
    }

    return { nodes: layout(rawNodes, rawEdges), edges: rawEdges };
  }, [generations, setSearchParams]);

  const fitTrigger = `${nodes.length}:${edges.length}`;
  useEffect(() => {
    void fitTrigger;
    const id = window.setTimeout(() => fitView({ padding: 0.18, duration: 180 }), 120);
    return () => window.clearTimeout(id);
  }, [fitView, fitTrigger]);

  return (
    <div className="h-full min-h-[620px] p-4">
      <div className="h-full min-h-[580px] overflow-hidden rounded-lg border border-border bg-bg-1">
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
          {nodes.length > 15 ? (
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
    </div>
  );
}

function LineageNode({ data }: NodeProps) {
  const node = data as LineageNodeData;
  return (
    <button
      type="button"
      onClick={node.onSelect}
      className="w-[190px] rounded-md border border-border bg-bg-2 p-2 text-left text-[12px] shadow-[var(--shadow-card-soft)] transition-colors hover:border-border-strong"
      style={{
        borderColor: node.winner ? "var(--qual-7)" : "var(--color-border)",
      }}
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="font-mono text-text">gen {node.generation}</span>
        <span className={node.winner ? "text-[--color-ok]" : "text-muted"}>
          {node.score == null ? "-" : node.score.toFixed(3)}
        </span>
      </div>
      <div className="truncate font-mono text-[11px] text-muted">{node.op}</div>
      <div className="truncate text-[11px] text-muted-2">{node.path || "root"}</div>
    </button>
  );
}

function layout(nodes: Node<LineageNodeData>[], edges: Edge[]): Node<LineageNodeData>[] {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "TB", nodesep: 36, ranksep: 72, marginx: 40, marginy: 40 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) graph.setNode(node.id, { width: 190, height: 76 });
  for (const edge of edges) graph.setEdge(edge.source, edge.target);
  dagre.layout(graph);
  return nodes.map((node) => {
    const point = graph.node(node.id);
    if (!point) return node;
    return {
      ...node,
      position: { x: point.x - 95, y: point.y - 38 },
    };
  });
}

function bestSurvivorIndex(generation: EvoGeneration): number {
  const candidates = generation.survivorIndices.length > 0 ? generation.survivorIndices : [0];
  return candidates.reduce((best, candidate) => {
    const bestScore = generation.scores[best] ?? Number.NEGATIVE_INFINITY;
    const candidateScore = generation.scores[candidate] ?? Number.NEGATIVE_INFINITY;
    return candidateScore > bestScore ? candidate : best;
  }, candidates[0] ?? 0);
}

function mutationFor(generation: EvoGeneration, individualId: number): EvoMutation | null {
  return generation.mutations.find((mutation) => mutation.individualId === individualId) ?? null;
}

function nodeId(generation: number, survivorIndex: number): string {
  return `gen-${generation}-survivor-${survivorIndex}`;
}

function edgeLabel(mutation: EvoMutation | null): string {
  if (!mutation) return "identity";
  return mutation.path ? `${mutation.op}(${mutation.path})` : mutation.op;
}
