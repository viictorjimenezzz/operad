import type { IoAgentEdge, IoComposite, IoGraphResponse } from "@/lib/types";

export interface CompositeGroup {
  path: string;
  className: string;
  /** Immediate composite/leaf children paths from the io_graph composites array. */
  childPaths: string[];
  /** Leaf agent paths transitively contained in this composite (used by super-edges). */
  leafPaths: string[];
  parentPath: string | null;
  collapsed: boolean;
}

/**
 * Build the composite tree from `IoGraphResponse.composites`. Every composite
 * starts collapsed. The order is deterministic (sorted by path).
 */
export function deriveCompositeGroups(ioGraph: IoGraphResponse): CompositeGroup[] {
  const composites = ioGraph.composites ?? [];
  const compositeByPath = new Map<string, IoComposite>();
  for (const c of composites) compositeByPath.set(c.path, c);

  const leafEdges = ioGraph.edges.filter((e) => e.kind !== "composite");
  const leafByPath = new Map<string, IoAgentEdge>();
  for (const e of leafEdges) leafByPath.set(e.agent_path, e);

  function collectLeafPaths(path: string): string[] {
    const c = compositeByPath.get(path);
    if (!c) {
      // Treat unknown paths as leaves (defensive — schema may drift).
      return leafByPath.has(path) ? [path] : [];
    }
    const out: string[] = [];
    for (const child of c.children) {
      if (compositeByPath.has(child)) {
        out.push(...collectLeafPaths(child));
      } else if (leafByPath.has(child)) {
        out.push(child);
      }
    }
    return out;
  }

  // Defensive fallback when the backend predates the composites field —
  // synthesize one composite per unique composite_path on the leaf edges.
  if (composites.length === 0) {
    const seen = new Map<string, CompositeGroup>();
    for (const e of leafEdges) {
      const path = e.composite_path;
      if (!path) continue;
      const current = seen.get(path) ?? {
        path,
        className: path.split(".").at(-1) ?? path,
        childPaths: [],
        leafPaths: [],
        parentPath: null,
        collapsed: true,
      };
      current.leafPaths.push(e.agent_path);
      current.childPaths = current.leafPaths;
      seen.set(path, current);
    }
    return [...seen.values()];
  }

  return composites
    .slice()
    .sort((a, b) => a.path.localeCompare(b.path))
    .map((c) => ({
      path: c.path,
      className: c.class_name,
      childPaths: c.children.slice(),
      leafPaths: collectLeafPaths(c.path),
      parentPath: c.parent_path,
      collapsed: true,
    }));
}

/**
 * Apply per-composite collapse state to an `IoGraphResponse`. Composites that
 * are collapsed render as a single super-edge (kind ``"composite"``) replacing
 * all leaf edges they transitively contain. Composites whose ancestor is
 * collapsed are absorbed into the ancestor's super-edge.
 */
export function applyCompositeCollapse(
  ioGraph: IoGraphResponse,
  groups: CompositeGroup[],
): IoGraphResponse {
  const groupByPath = new Map<string, CompositeGroup>();
  for (const g of groups) groupByPath.set(g.path, g);

  // For each composite, determine the closest collapsed ancestor (or self if
  // self is collapsed). If no collapsed ancestor exists, the composite is
  // "open" and its children are shown directly.
  function closestCollapsedAncestor(path: string | null): string | null {
    let curr = path;
    let lastCollapsed: string | null = null;
    while (curr) {
      const g = groupByPath.get(curr);
      if (g?.collapsed) lastCollapsed = curr;
      curr = g?.parentPath ?? null;
    }
    return lastCollapsed;
  }

  const leafEdges = ioGraph.edges.filter((e) => e.kind !== "composite");

  // Bucket leaf edges by their closest collapsed ancestor; un-bucketed ones
  // are visible directly.
  const passthrough: IoAgentEdge[] = [];
  const buckets = new Map<string, IoAgentEdge[]>();
  for (const e of leafEdges) {
    const collapsedAncestor = closestCollapsedAncestor(e.composite_path ?? null);
    if (!collapsedAncestor) {
      passthrough.push(e);
      continue;
    }
    const arr = buckets.get(collapsedAncestor) ?? [];
    arr.push(e);
    buckets.set(collapsedAncestor, arr);
  }

  // Build a super-edge per bucket. The super-edge spans from the bucket's
  // earliest input type (sourced from the first member edge) to its latest
  // output type (the last member edge), preserving edge ordering.
  const superEdges: IoAgentEdge[] = [];
  for (const [path, members] of buckets) {
    if (members.length === 0) continue;
    const group = groupByPath.get(path);
    const first = members[0];
    const last = members[members.length - 1];
    if (!first || !last || !group) continue;
    superEdges.push({
      agent_path: `${path}.__collapsed__`,
      class_name: group.className,
      kind: "composite",
      from: first.from,
      to: last.to,
      composite_path: path,
    });
  }

  return {
    ...ioGraph,
    edges: [...passthrough, ...superEdges],
  };
}

/**
 * Expand or collapse a single composite by path. Returns a new groups array.
 */
export function toggleComposite(
  groups: CompositeGroup[],
  path: string,
): CompositeGroup[] {
  return groups.map((g) => (g.path === path ? { ...g, collapsed: !g.collapsed } : g));
}
