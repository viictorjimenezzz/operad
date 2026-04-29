import {
  type EvoGeneration,
  type EvoIndividual,
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
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

interface EvoLineageTabProps {
  summary?: unknown;
  fitness?: unknown;
  events?: unknown;
}

export interface FocusedLineageNode {
  id: string;
  kind: "individual" | "discarded";
  generation: number;
  lineageId: string | null;
  parentLineageId: string | null;
  individualId: number | null;
  score: number | null;
  selected: boolean;
  winner: boolean;
  op: string;
  path: string;
  count: number;
  groupId: string | null;
}

export interface FocusedLineageEdge {
  id: string;
  source: string;
  target: string;
  winner: boolean;
}

export interface FocusedLineageGraph {
  nodes: FocusedLineageNode[];
  edges: FocusedLineageEdge[];
}

interface LineageNodeData extends Record<string, unknown> {
  node: FocusedLineageNode;
  onSelect: () => void;
}

interface DiscardNodeData extends Record<string, unknown> {
  node: FocusedLineageNode;
  expanded: boolean;
  onToggle: () => void;
}

const NODE_WIDTH = 210;
const NODE_HEIGHT = 94;
const GROUP_WIDTH = 160;
const GROUP_HEIGHT = 56;

const nodeTypes = {
  lineage: LineageNode,
  discarded: DiscardedNode,
};

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
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => new Set());
  const [, setSearchParams] = useSearchParams();
  const { fitView } = useReactFlow();

  const graph = useMemo(
    () => buildFocusedLineageGraph(generations, expandedGroups),
    [generations, expandedGroups],
  );

  const { nodes, edges } = useMemo(() => {
    const rawNodes: Node<LineageNodeData | DiscardNodeData>[] = graph.nodes.map((node) => {
      const isGroup = node.kind === "discarded";
      return {
        id: node.id,
        type: isGroup ? "discarded" : "lineage",
        position: { x: 0, y: 0 },
        data: isGroup
          ? {
              node,
              expanded: node.groupId != null && expandedGroups.has(node.groupId),
              onToggle: () => {
                if (!node.groupId) return;
                setExpandedGroups((current) => {
                  const next = new Set(current);
                  if (next.has(node.groupId as string)) next.delete(node.groupId as string);
                  else next.add(node.groupId as string);
                  return next;
                });
              },
            }
          : {
              node,
              onSelect: () =>
                setSearchParams(
                  (current) => {
                    const next = new URLSearchParams(current);
                    next.set("tab", "population");
                    next.set("gen", String(node.generation));
                    if (node.individualId != null) {
                      next.set("individual", String(node.individualId));
                    }
                    return next;
                  },
                  { replace: false },
                ),
            },
      };
    });
    const rawEdges: Edge[] = graph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: edge.winner,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke: edge.winner ? "var(--qual-7)" : "var(--color-border-strong)",
        strokeWidth: edge.winner ? 2.4 : 1.2,
        opacity: edge.winner ? 0.95 : 0.5,
      },
    }));
    return { nodes: layout(rawNodes, rawEdges), edges: rawEdges };
  }, [expandedGroups, graph, setSearchParams]);

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
          minZoom={0.18}
          maxZoom={1.35}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={24} />
          {nodes.length > 18 ? (
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

export function buildFocusedLineageGraph(
  generations: EvoGeneration[],
  expandedGroups: Set<string> = new Set(),
): FocusedLineageGraph {
  const nodes: FocusedLineageNode[] = [];
  const edges: FocusedLineageEdge[] = [];
  const visibleByGeneration = new Map<number, FocusedLineageNode[]>();
  const collapsedGroups = new Map<string, FocusedLineageNode>();

  for (const generation of generations) {
    for (const individual of generationIndividuals(generation)) {
      const groupId = discardGroupId(generation.genIndex, individual.parentLineageId);
      const visible = individual.selected || expandedGroups.has(groupId);
      if (!visible) {
        const existing = collapsedGroups.get(groupId);
        if (existing) {
          existing.count += 1;
          if (existing.score == null || (individual.score ?? Number.NEGATIVE_INFINITY) > existing.score) {
            existing.score = individual.score;
          }
        } else {
          const groupNode: FocusedLineageNode = {
            id: groupId,
            kind: "discarded",
            generation: generation.genIndex,
            lineageId: null,
            parentLineageId: individual.parentLineageId,
            individualId: null,
            score: individual.score,
            selected: false,
            winner: false,
            op: "discarded",
            path: "",
            count: 1,
            groupId,
          };
          collapsedGroups.set(groupId, groupNode);
          nodes.push(groupNode);
          addVisible(visibleByGeneration, groupNode);
        }
        continue;
      }

      const node: FocusedLineageNode = {
        id: individualNodeId(generation.genIndex, individual),
        kind: "individual",
        generation: generation.genIndex,
        lineageId: individual.lineageId,
        parentLineageId: individual.parentLineageId,
        individualId: individual.individualId,
        score: individual.score,
        selected: individual.selected,
        winner: generation.selectedLineageId === individual.lineageId,
        op: individual.op,
        path: individual.path,
        count: 1,
        groupId: null,
      };
      nodes.push(node);
      addVisible(visibleByGeneration, node);
    }
  }

  for (const node of nodes) {
    const source = parentNodeFor(node, visibleByGeneration);
    if (!source) continue;
    edges.push({
      id: `${source.id}->${node.id}`,
      source: source.id,
      target: node.id,
      winner: node.winner && source.winner,
    });
  }

  return { nodes, edges };
}

function LineageNode({ data }: NodeProps) {
  const { node, onSelect } = data as LineageNodeData;
  return (
    <button
      type="button"
      onClick={onSelect}
      className="w-[210px] rounded-md border bg-bg-2 p-2 text-left text-[12px] shadow-[var(--shadow-card-soft)] transition-colors hover:border-border-strong"
      style={{ borderColor: node.winner ? "var(--qual-7)" : "var(--color-border)" }}
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="font-mono text-text">
          gen {node.generation} / ind {node.individualId}
        </span>
        <span className={node.winner ? "text-[--color-ok]" : "text-muted"}>
          {node.score == null ? "-" : node.score.toFixed(3)}
        </span>
      </div>
      <div className="truncate font-mono text-[11px] text-muted">{node.op}</div>
      <div className="truncate text-[11px] text-muted-2">{node.path || "root"}</div>
      <div className="mt-1 flex items-center justify-between gap-2 font-mono text-[10px] text-muted-2">
        <span>{shortLineage(node.lineageId)}</span>
        <span>{node.selected ? "selected" : "candidate"}</span>
      </div>
    </button>
  );
}

function DiscardedNode({ data }: NodeProps) {
  const { node, onToggle } = data as DiscardNodeData;
  return (
    <button
      type="button"
      onClick={onToggle}
      className="w-[160px] rounded-md border border-border border-dashed bg-bg-inset px-2 py-2 text-left text-[12px] text-muted transition-colors hover:border-border-strong hover:text-text"
    >
      <div className="font-mono text-text">gen {node.generation}</div>
      <div className="font-mono text-[11px]">{node.count} discarded</div>
      <div className="truncate text-[10px] text-muted-2">
        parent {shortLineage(node.parentLineageId)}
      </div>
    </button>
  );
}

function layout<T extends Record<string, unknown>>(nodes: Node<T>[], edges: Edge[]): Node<T>[] {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "LR", nodesep: 42, ranksep: 82, marginx: 48, marginy: 48 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) {
    const isGroup = node.type === "discarded";
    graph.setNode(node.id, {
      width: isGroup ? GROUP_WIDTH : NODE_WIDTH,
      height: isGroup ? GROUP_HEIGHT : NODE_HEIGHT,
    });
  }
  for (const edge of edges) graph.setEdge(edge.source, edge.target);
  dagre.layout(graph);
  return nodes.map((node) => {
    const point = graph.node(node.id);
    if (!point) return node;
    const isGroup = node.type === "discarded";
    const width = isGroup ? GROUP_WIDTH : NODE_WIDTH;
    const height = isGroup ? GROUP_HEIGHT : NODE_HEIGHT;
    return { ...node, position: { x: point.x - width / 2, y: point.y - height / 2 } };
  });
}

function generationIndividuals(generation: EvoGeneration): EvoIndividual[] {
  if (generation.individuals.length > 0) return generation.individuals;
  const survivorSet = new Set(generation.survivorIndices);
  return generation.scores.map((score, individualId) => ({
    individualId,
    lineageId: `legacy-${generation.genIndex}-${individualId}`,
    parentLineageId: null,
    score,
    selected: survivorSet.has(individualId),
    op: "identity",
    path: "",
    improved: false,
    parameterDeltas: [],
  }));
}

function addVisible(
  byGeneration: Map<number, FocusedLineageNode[]>,
  node: FocusedLineageNode,
) {
  const current = byGeneration.get(node.generation);
  if (current) current.push(node);
  else byGeneration.set(node.generation, [node]);
}

function parentNodeFor(
  node: FocusedLineageNode,
  byGeneration: Map<number, FocusedLineageNode[]>,
): FocusedLineageNode | null {
  for (let gen = node.generation - 1; gen >= 0; gen -= 1) {
    const candidates = byGeneration.get(gen) ?? [];
    const sameLineage =
      node.lineageId != null
        ? candidates.find((candidate) => candidate.lineageId === node.lineageId)
        : null;
    if (sameLineage) return sameLineage;
    const parent =
      node.parentLineageId != null
        ? candidates.find((candidate) => candidate.lineageId === node.parentLineageId)
        : null;
    if (parent) return parent;
  }
  return null;
}

function individualNodeId(generation: number, individual: EvoIndividual): string {
  return `gen-${generation}-lineage-${individual.lineageId}-ind-${individual.individualId}`;
}

function discardGroupId(generation: number, parentLineageId: string | null): string {
  return `discarded-${generation}-${parentLineageId ?? "root"}`;
}

function shortLineage(value: string | null): string {
  if (!value) return "root";
  return value.length <= 8 ? value : `${value.slice(0, 8)}...`;
}
