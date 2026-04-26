import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

const NODE_WIDTH_MIN = 200;
const NODE_WIDTH_MAX = 280;
const NODE_HEIGHT_BASE = 78;
const FIELD_ROW_PX = 16;

export function widthForFields(fieldCount: number): number {
  // 200..280 px depending on field count; capped.
  return Math.min(NODE_WIDTH_MAX, Math.max(NODE_WIDTH_MIN, 200 + Math.min(fieldCount, 10) * 6));
}

export function heightForFields(fieldCount: number, previewCount = 3): number {
  return NODE_HEIGHT_BASE + Math.min(previewCount, fieldCount) * FIELD_ROW_PX;
}

export interface LayoutOptions {
  /** Force a direction; otherwise inferred from depth/breadth. */
  direction?: "TB" | "LR";
  /** Field counts per node id, used to pick width/height. */
  fieldCounts?: Record<string, number>;
}

export function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  options: LayoutOptions = {},
): Node[] {
  const fieldCounts = options.fieldCounts ?? {};
  const direction = options.direction ?? inferDirection(nodes, edges);

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction,
    nodesep: direction === "TB" ? 32 : 24,
    ranksep: direction === "TB" ? 56 : 48,
    marginx: 32,
    marginy: 32,
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) {
    const count = fieldCounts[n.id] ?? 0;
    g.setNode(n.id, { width: widthForFields(count), height: heightForFields(count) });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const point = g.node(node.id);
    if (!point) return node;
    return {
      ...node,
      position: {
        x: point.x - point.width / 2,
        y: point.y - point.height / 2,
      },
    };
  });
}

function inferDirection(nodes: Node[], edges: Edge[]): "TB" | "LR" {
  if (nodes.length === 0) return "LR";
  // Build adjacency, count longest path length (rough proxy for depth).
  const out = new Map<string, string[]>();
  for (const e of edges) {
    if (!out.has(e.source)) out.set(e.source, []);
    out.get(e.source)?.push(e.target);
  }
  // Find roots (no incoming edges).
  const incoming = new Set(edges.map((e) => e.target));
  const roots = nodes.filter((n) => !incoming.has(n.id)).map((n) => n.id);
  let maxDepth = 0;
  const memo = new Map<string, number>();
  const visit = (id: string, seen: Set<string>): number => {
    if (memo.has(id)) return memo.get(id) ?? 0;
    if (seen.has(id)) return 0;
    seen.add(id);
    const children = out.get(id) ?? [];
    let best = 0;
    for (const c of children) best = Math.max(best, 1 + visit(c, seen));
    memo.set(id, best);
    return best;
  };
  for (const r of roots) maxDepth = Math.max(maxDepth, visit(r, new Set()));
  // Wide & shallow → LR. Deep & narrow → TB.
  return maxDepth >= 4 ? "TB" : "LR";
}
