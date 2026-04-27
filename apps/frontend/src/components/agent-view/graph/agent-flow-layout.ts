import type { AgentFlowEdge, AgentFlowNode } from "@/lib/types";
import dagre from "@dagrejs/dagre";

const LEAF_W = 168;
const LEAF_H = 56;
const COMPOSITE_HEADER_H = 28;
const COMPOSITE_PADDING = 16;
const COMPOSITE_W_MIN = 220;
const COMPOSITE_H_MIN = 80;

export interface LayoutInput {
  nodes: AgentFlowNode[];
  edges: AgentFlowEdge[];
  rootPath: string | null;
  /** Map from composite path → expanded? Composites missing from the map are collapsed. */
  expanded: Set<string>;
}

export interface PositionedNode {
  path: string;
  parent_path: string | null;
  kind: "leaf" | "composite";
  className: string;
  inputLabel: string;
  outputLabel: string;
  width: number;
  height: number;
  x: number;
  y: number;
  /** When kind === "composite", true means it's currently expanded (renders as a group container). */
  expanded: boolean;
  /** True iff this node is hidden because an ancestor is collapsed. */
  hidden: boolean;
}

export interface PositionedEdge {
  caller: string;
  callee: string;
  type: string;
  /** When true, this edge is rendered. */
  visible: boolean;
}

export interface LayoutResult {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
}

/**
 * Compute hierarchical positions for the agent-flow graph using compound Dagre.
 * - Composites that are NOT expanded render as a single rectangle (their
 *   children are hidden and incoming/outgoing edges are rerouted to/from
 *   the composite itself).
 * - Composites that ARE expanded render as a translucent container with
 *   children laid out inside (Dagre compound graph).
 */
export function layoutAgentFlow({ nodes, edges, rootPath, expanded }: LayoutInput): LayoutResult {
  if (nodes.length === 0) {
    return { nodes: [], edges: [] };
  }
  const nodeByPath = new Map<string, AgentFlowNode>();
  for (const n of nodes) nodeByPath.set(n.path, n);

  // For every node, walk up parents and check if any ancestor is collapsed.
  // A node is "rendered" only when all ancestors are expanded.
  function isHidden(path: string): boolean {
    let curr: string | null = nodeByPath.get(path)?.parent_path ?? null;
    while (curr) {
      const isExpanded = expanded.has(curr);
      const isRoot = curr === rootPath;
      if (!isExpanded && !isRoot) return true;
      curr = nodeByPath.get(curr)?.parent_path ?? null;
    }
    return false;
  }

  // For a hidden leaf, find the closest visible ancestor (the collapsed
  // composite that represents it on the canvas). Returns the original path
  // if the node itself is visible.
  function visibleAncestor(path: string): string {
    if (visibleNodePaths.has(path)) return path;
    let curr = path;
    while (curr) {
      const node = nodeByPath.get(curr);
      if (!node) return curr;
      const parent = node.parent_path;
      if (!parent) return curr;
      if (parent === rootPath) return curr;
      if (!expanded.has(parent)) {
        // parent is collapsed → ancestor represents this node
        return parent;
      }
      curr = parent;
    }
    return path;
  }

  const visibleNodePaths = new Set<string>();
  for (const n of nodes) {
    if (n.path === rootPath) continue; // root doesn't render as a node here
    if (!isHidden(n.path)) visibleNodePaths.add(n.path);
  }

  // Build Dagre compound graph for visible nodes.
  const g = new dagre.graphlib.Graph({ compound: true });
  g.setGraph({ rankdir: "LR", nodesep: 24, ranksep: 64, marginx: 16, marginy: 16 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const path of visibleNodePaths) {
    const n = nodeByPath.get(path);
    if (!n) continue;
    if (n.kind === "composite" && expanded.has(path)) {
      // Expanded composite: parent in Dagre, will size to fit children.
      g.setNode(path, {
        label: n.class_name,
        width: COMPOSITE_W_MIN,
        height: COMPOSITE_H_MIN,
        clusterLabelPos: "top",
        paddingTop: COMPOSITE_HEADER_H + 8,
        paddingBottom: COMPOSITE_PADDING,
        paddingLeft: COMPOSITE_PADDING,
        paddingRight: COMPOSITE_PADDING,
      });
    } else {
      g.setNode(path, { label: n.class_name, width: LEAF_W, height: LEAF_H });
    }
  }
  // Set parent relationships for nested visibility (compound graph).
  for (const path of visibleNodePaths) {
    const n = nodeByPath.get(path);
    if (!n || !n.parent_path) continue;
    if (n.parent_path === rootPath) continue;
    if (visibleNodePaths.has(n.parent_path) && expanded.has(n.parent_path)) {
      g.setParent(path, n.parent_path);
    }
  }

  function isContainmentEdge(a: string, b: string): boolean {
    return isAncestorOf(a, b) || isAncestorOf(b, a);
  }

  function isAncestorOf(ancestor: string, path: string): boolean {
    let curr = nodeByPath.get(path)?.parent_path ?? null;
    while (curr) {
      if (curr === ancestor) return true;
      curr = nodeByPath.get(curr)?.parent_path ?? null;
    }
    return false;
  }

  // Edge routing: each original edge, after collapse, connects two
  // visible-ancestor paths.
  const remappedEdges = new Map<string, { caller: string; callee: string; type: string }>();
  for (const e of edges) {
    const a = visibleAncestor(e.caller);
    const b = visibleAncestor(e.callee);
    if (a === b) continue; // self-loop after collapse
    if (isContainmentEdge(a, b)) continue;
    if (!visibleNodePaths.has(a) || !visibleNodePaths.has(b)) continue;
    const key = `${a}::${b}::${e.type}`;
    if (!remappedEdges.has(key)) {
      remappedEdges.set(key, { caller: a, callee: b, type: e.type });
    }
  }
  for (const e of remappedEdges.values()) {
    g.setEdge(e.caller, e.callee);
  }

  try {
    dagre.layout(g);
  } catch {
    return fallbackLayout({
      nodes,
      rootPath,
      expanded,
      visibleNodePaths,
      visibleAncestor,
      isContainmentEdge,
      edges,
    });
  }

  const positioned: PositionedNode[] = [];
  for (const n of nodes) {
    if (n.path === rootPath) continue;
    const visible = visibleNodePaths.has(n.path);
    const point = visible ? g.node(n.path) : undefined;
    positioned.push({
      path: n.path,
      parent_path: n.parent_path,
      kind: n.kind,
      className: n.class_name,
      inputLabel: n.input_label,
      outputLabel: n.output_label,
      width: point?.width ?? LEAF_W,
      height: point?.height ?? LEAF_H,
      x: point ? point.x - point.width / 2 : 0,
      y: point ? point.y - point.height / 2 : 0,
      expanded: n.kind === "composite" && expanded.has(n.path),
      hidden: !visible,
    });
  }

  const edgesOut: PositionedEdge[] = [];
  for (const e of edges) {
    const a = visibleAncestor(e.caller);
    const b = visibleAncestor(e.callee);
    edgesOut.push({
      caller: a,
      callee: b,
      type: e.type,
      visible:
        a !== b && visibleNodePaths.has(a) && visibleNodePaths.has(b) && !isContainmentEdge(a, b),
    });
  }

  return { nodes: positioned, edges: edgesOut };
}

function fallbackLayout({
  nodes,
  rootPath,
  expanded,
  visibleNodePaths,
  visibleAncestor,
  isContainmentEdge,
  edges,
}: {
  nodes: AgentFlowNode[];
  rootPath: string | null;
  expanded: Set<string>;
  visibleNodePaths: Set<string>;
  visibleAncestor: (path: string) => string;
  isContainmentEdge: (a: string, b: string) => boolean;
  edges: AgentFlowEdge[];
}): LayoutResult {
  let row = 0;
  const positioned: PositionedNode[] = [];
  for (const n of nodes) {
    if (n.path === rootPath) continue;
    const visible = visibleNodePaths.has(n.path);
    const depth = visible ? pathDepth(n.path, nodes) : 0;
    const isExpandedComposite = n.kind === "composite" && expanded.has(n.path);
    const width = isExpandedComposite ? COMPOSITE_W_MIN : LEAF_W;
    const height = isExpandedComposite ? COMPOSITE_H_MIN : LEAF_H;
    positioned.push({
      path: n.path,
      parent_path: n.parent_path,
      kind: n.kind,
      className: n.class_name,
      inputLabel: n.input_label,
      outputLabel: n.output_label,
      width,
      height,
      x: visible ? 32 + depth * 240 : 0,
      y: visible ? 32 + row++ * 96 : 0,
      expanded: isExpandedComposite,
      hidden: !visible,
    });
  }

  return {
    nodes: positioned,
    edges: edges.map((e) => {
      const a = visibleAncestor(e.caller);
      const b = visibleAncestor(e.callee);
      return {
        caller: a,
        callee: b,
        type: e.type,
        visible:
          a !== b && visibleNodePaths.has(a) && visibleNodePaths.has(b) && !isContainmentEdge(a, b),
      };
    }),
  };
}

function pathDepth(path: string, nodes: AgentFlowNode[]): number {
  const nodeByPath = new Map(nodes.map((n) => [n.path, n]));
  let depth = 0;
  let curr = nodeByPath.get(path)?.parent_path ?? null;
  while (curr) {
    depth += 1;
    curr = nodeByPath.get(curr)?.parent_path ?? null;
  }
  return depth;
}
