import type { IoGraphResponse } from "@/lib/types";

export interface CompositeGroup {
  path: string;
  className: string;
  edges: string[];
  collapsed: boolean;
}

export function deriveCompositeGroups(ioGraph: IoGraphResponse): CompositeGroup[] {
  const map = new Map<string, CompositeGroup>();
  for (const edge of ioGraph.edges) {
    const path = edge.composite_path ?? "";
    if (!path) continue;
    const current = map.get(path) ?? {
      path,
      className: path.split(".").at(-1) ?? path,
      edges: [],
      collapsed: true,
    };
    current.edges.push(edge.agent_path);
    map.set(path, current);
  }
  return [...map.values()];
}

export function applyCompositeCollapse(
  ioGraph: IoGraphResponse,
  groups: CompositeGroup[],
): IoGraphResponse {
  const collapsedSet = new Set(groups.filter((g) => g.collapsed).flatMap((g) => g.edges));
  const collapsedByPath = new Map(groups.filter((g) => g.collapsed).map((g) => [g.path, g]));

  const passthroughEdges = ioGraph.edges.filter((e) => !collapsedSet.has(e.agent_path));
  const superEdges = [...collapsedByPath.entries()].flatMap(([path, group]) => {
    const members = ioGraph.edges.filter((e) => e.composite_path === path);
    if (members.length === 0) return [];
    const first = members[0];
    const last = members[members.length - 1];
    if (!first || !last) return [];
    return [
      {
        agent_path: `${path}.__collapsed__`,
        class_name: group.className,
        kind: "composite",
        from: first.from,
        to: last.to,
        composite_path: path,
      },
    ];
  });

  return {
    ...ioGraph,
    edges: [...passthroughEdges, ...superEdges],
  };
}
