import {
  asRecord,
  buildEvoGenerations,
  type EvoGeneration,
  type EvoMutation,
  stringValue,
} from "@/components/algorithms/evogradient/evo-detail-overview";
import { EmptyState } from "@/components/ui";
import { type ChildRunSummary, useChildren } from "@/hooks/use-children";
import { useMemo } from "react";

interface EvoLineageTabProps {
  summary?: unknown;
  fitness?: unknown;
  events?: unknown;
}

interface LineageNode {
  id: string;
  genIndex: number;
  individualId: number;
  score: number | null;
  op: string;
  path: string;
  x: number;
  y: number;
  color: string;
  parentId: string | null;
}

interface LineageEdge {
  id: string;
  sourceId: string;
  targetId: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
}

interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
  width: number;
  height: number;
  maxIndividuals: number;
}

const MARGIN_LEFT = 84;
const MARGIN_RIGHT = 24;
const MARGIN_TOP = 40;
const MARGIN_BOTTOM = 36;
const COLUMN_GAP = 180;
const ROW_GAP = 44;
const NODE_RADIUS = 10;

export function EvoLineageTab({ summary, fitness, events }: EvoLineageTabProps) {
  const generations = buildEvoGenerations(summary, fitness, events);
  const runId = stringValue(asRecord(summary)?.run_id);
  const children = useChildren(runId);

  const childHrefByKey = useMemo(() => {
    const out = new Map<string, string>();
    for (const child of children.data ?? []) {
      const gen = numberFromMetadata(child, "gen") ?? numberFromMetadata(child, "gen_index");
      const individual = numberFromMetadata(child, "individual_id");
      if (gen == null || individual == null) continue;
      out.set(`${gen}:${individual}`, childRoute(child));
    }
    return out;
  }, [children.data]);

  if (generations.length === 0) {
    return (
      <EmptyState
        title="no lineage data"
        description="lineage appears after EvoGradient emits generation events"
      />
    );
  }

  const graph = buildLineageGraph(generations);

  return (
    <div className="h-full overflow-auto p-4">
      <svg
        width={Math.max(graph.width, 920)}
        height={Math.max(graph.height, 360)}
        role="img"
        aria-label="evogradient lineage graph"
      >
        <g>
          {generations.map((generation) => (
            <text
              key={`gen-label-${generation.genIndex}`}
              x={MARGIN_LEFT + generation.genIndex * COLUMN_GAP}
              y={20}
              textAnchor="middle"
              className="fill-muted font-mono text-[11px]"
            >
              {`gen ${generation.genIndex}`}
            </text>
          ))}
          {Array.from({ length: graph.maxIndividuals }).map((_, index) => (
            <text
              key={`individual-label-${index}`}
              x={MARGIN_LEFT - 24}
              y={MARGIN_TOP + index * ROW_GAP + 4}
              textAnchor="end"
              className="fill-muted font-mono text-[10px]"
            >
              {index}
            </text>
          ))}
        </g>

        <g>
          {graph.edges.map((edge) => (
            <path
              key={edge.id}
              d={edgePath(edge)}
              fill="none"
              stroke="var(--color-border-strong)"
              strokeWidth={1.2}
              opacity={0.75}
            />
          ))}
        </g>

        <g>
          {graph.nodes.map((node) => {
            const href = childHrefByKey.get(`${node.genIndex}:${node.individualId}`);
            const title = [
              `gen ${node.genIndex} · individual ${node.individualId}`,
              `score ${node.score == null ? "-" : node.score.toFixed(4)}`,
              `op ${mutationLabel(node.op, node.path)}`,
            ].join("\n");

            const content = (
              <g>
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={NODE_RADIUS}
                  fill={node.color}
                  stroke={href ? "var(--color-accent)" : "var(--color-border)"}
                  strokeWidth={href ? 1.8 : 1.1}
                >
                  <title>{title}</title>
                </circle>
              </g>
            );

            if (!href) {
              return <g key={node.id}>{content}</g>;
            }

            return (
              <a key={node.id} href={href} aria-label={`open child run for gen ${node.genIndex} individual ${node.individualId}`}>
                {content}
              </a>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

export function buildLineageGraph(generations: EvoGeneration[]): LineageGraph {
  const nodes: LineageNode[] = [];
  const edges: LineageEdge[] = [];
  const maxIndividuals = Math.max(...generations.map((generation) => generation.scores.length), 0);

  let minScore = Number.POSITIVE_INFINITY;
  let maxScore = Number.NEGATIVE_INFINITY;
  for (const generation of generations) {
    for (const score of generation.scores) {
      if (score < minScore) minScore = score;
      if (score > maxScore) maxScore = score;
    }
  }
  const hasScoreRange = Number.isFinite(minScore) && Number.isFinite(maxScore);

  for (let genIndex = 0; genIndex < generations.length; genIndex += 1) {
    const generation = generations[genIndex];
    if (!generation) continue;
    const scores = generation?.scores ?? [];
    for (let individualId = 0; individualId < scores.length; individualId += 1) {
      const score = scores[individualId] ?? null;
      const mutation = mutationFor(generation, individualId);
      const parentIndividual =
        genIndex === 0
          ? null
          : parentIndividualId(generations[genIndex - 1], individualId, maxIndividuals);
      const parentId =
        parentIndividual == null ? null : nodeId(genIndex - 1, parentIndividual);

      const x = MARGIN_LEFT + genIndex * COLUMN_GAP;
      const y = MARGIN_TOP + individualId * ROW_GAP;
      const id = nodeId(genIndex, individualId);

      nodes.push({
        id,
        genIndex,
        individualId,
        score,
        op: mutation?.op ?? "identity",
        path: mutation?.path ?? "",
        x,
        y,
        color: scoreColor(score, minScore, maxScore, hasScoreRange),
        parentId,
      });

      if (parentId != null && parentIndividual != null) {
        const sourceX = MARGIN_LEFT + (genIndex - 1) * COLUMN_GAP;
        const sourceY = MARGIN_TOP + parentIndividual * ROW_GAP;
        edges.push({
          id: `${parentId}->${id}`,
          sourceId: parentId,
          targetId: id,
          sourceX,
          sourceY,
          targetX: x,
          targetY: y,
        });
      }
    }
  }

  const width = MARGIN_LEFT + MARGIN_RIGHT + Math.max(0, generations.length - 1) * COLUMN_GAP;
  const height = MARGIN_TOP + MARGIN_BOTTOM + Math.max(0, maxIndividuals - 1) * ROW_GAP;

  return { nodes, edges, width, height, maxIndividuals };
}

function mutationFor(generation: EvoGeneration, individualId: number): EvoMutation | null {
  return generation.mutations.find((mutation) => mutation.individualId === individualId) ?? null;
}

function parentIndividualId(
  previousGeneration: EvoGeneration | undefined,
  childIndividualId: number,
  maxIndividuals: number,
): number {
  const previousSize = previousGeneration?.scores.length ?? maxIndividuals;
  if (previousSize <= 0) return 0;
  const fallback = Math.min(childIndividualId, previousSize - 1);
  const survivors = previousGeneration?.survivorIndices ?? [];
  if (survivors.length === 0) return fallback;
  const candidate = survivors[childIndividualId % survivors.length];
  return typeof candidate === "number" && Number.isFinite(candidate)
    ? Math.max(0, Math.min(candidate, previousSize - 1))
    : fallback;
}

function scoreColor(
  score: number | null,
  min: number,
  max: number,
  hasRange: boolean,
): string {
  if (score == null || !hasRange) return "var(--color-muted-2)";
  if (max <= min) return "color-mix(in srgb, var(--color-err) 50%, var(--color-ok) 50%)";
  const ratio = Math.max(0, Math.min(1, (score - min) / (max - min)));
  const okPct = Math.round(ratio * 100);
  const errPct = 100 - okPct;
  return `color-mix(in srgb, var(--color-err) ${errPct}%, var(--color-ok) ${okPct}%)`;
}

function edgePath(edge: LineageEdge): string {
  const controlDelta = (edge.targetX - edge.sourceX) * 0.45;
  const c1x = edge.sourceX + controlDelta;
  const c2x = edge.targetX - controlDelta;
  return `M ${edge.sourceX} ${edge.sourceY} C ${c1x} ${edge.sourceY}, ${c2x} ${edge.targetY}, ${edge.targetX} ${edge.targetY}`;
}

function mutationLabel(op: string, path: string): string {
  return path.length > 0 ? `${op}(${path})` : op;
}

function nodeId(genIndex: number, individualId: number): string {
  return `gen-${genIndex}-ind-${individualId}`;
}

function childRoute(child: ChildRunSummary): string {
  const hash =
    child.hash_content ??
    stringAt(child.metadata, "hash_content") ??
    stringAt(child.parent_run_metadata, "hash_content") ??
    child.root_agent_path ??
    child.run_id;

  if (child.algorithm_path === "OPRO") return `/opro/${encodeURIComponent(child.run_id)}`;
  if (child.algorithm_path === "Trainer" || child.algorithm_path?.endsWith(".Trainer")) {
    return `/training/${encodeURIComponent(child.run_id)}`;
  }
  if (child.is_algorithm) return `/algorithms/${encodeURIComponent(child.run_id)}`;
  return `/agents/${encodeURIComponent(hash)}/runs/${encodeURIComponent(child.run_id)}`;
}

function numberFromMetadata(child: ChildRunSummary, key: string): number | null {
  return (
    numberAt(child.algorithm_metadata, key) ??
    numberAt(child.parent_run_metadata, key) ??
    numberAt(child.metadata, key)
  );
}

function numberAt(source: unknown, key: string): number | null {
  const value = valueAt(source, key);
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringAt(source: unknown, key: string): string | null {
  const value = valueAt(source, key);
  return typeof value === "string" && value.length > 0 ? value : null;
}

function valueAt(source: unknown, key: string): unknown {
  return source !== null && typeof source === "object" && !Array.isArray(source)
    ? (source as Record<string, unknown>)[key]
    : undefined;
}
