import { layoutAgentFlow } from "@/components/agent-view/graph/agent-flow-layout";
import { AgentNodeCard } from "@/components/agent-view/graph/agent-node-card";
import { CompositeFlowNode } from "@/components/agent-view/graph/composite-flow-node";
import { TypedEdge } from "@/components/agent-view/graph/typed-edge";
import { useActiveAgents } from "@/components/agent-view/graph/use-active-agents";
import { Button, EmptyState, IconButton } from "@/components/ui";
import { dashboardApi } from "@/lib/api/dashboard";
import type { AgentFlowEdge, AgentFlowNode, AgentGraphResponse } from "@/lib/types";
import { useUIStore } from "@/stores";
import { useQueries } from "@tanstack/react-query";
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
import { Copy, Maximize2, Minimize2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface AgentFlowGraphProps {
  agentGraph: AgentGraphResponse;
  runId: string;
}

const nodeTypes = { agent: AgentNodeCard, composite: CompositeFlowNode };
const edgeTypes = { typed: TypedEdge };
const FIT_VIEW_OPTIONS = { padding: 0.18, duration: 220 } as const;
const SINGLE_FIT_VIEW_OPTIONS = { padding: 0.45, duration: 180 } as const;
const MINIMAP_STYLE = {
  background: "var(--color-bg-1)",
  border: "1px solid var(--color-border)",
  borderRadius: 6,
} as const;

function normalizeAgentGraph(agentGraph: AgentGraphResponse): AgentGraphResponse {
  const seen = new Set<string>();
  const nodes: AgentFlowNode[] = [];

  for (const raw of agentGraph.nodes) {
    const path = raw.path.trim();
    if (!path || seen.has(path)) continue;
    seen.add(path);
    nodes.push({
      ...raw,
      path,
      class_name: raw.class_name.trim() || fallbackClassName(path, raw.kind),
      input_label: raw.input_label.trim() || raw.input.trim() || "input",
      output_label: raw.output_label.trim() || raw.output.trim() || "output",
      parent_path: raw.parent_path?.trim() || null,
    });
  }

  const root = agentGraph.root?.trim() || null;
  const paths = new Set(nodes.map((node) => node.path));
  const fixedNodes = nodes.map((node) => ({
    ...node,
    parent_path:
      node.parent_path && (paths.has(node.parent_path) || node.parent_path === root)
        ? node.parent_path
        : null,
  }));

  if (fixedNodes.length === 0) {
    return { root: null, nodes: [], edges: [] };
  }

  const visibleNodes = fixedNodes.filter((node) => node.path !== root);
  if (visibleNodes.length === 0) {
    const fallback = fixedNodes[0];
    if (!fallback) return { root: null, nodes: [], edges: [] };
    const fallbackNode: AgentFlowNode = {
      path: fallback.path,
      kind: "leaf",
      parent_path: null,
      input: fallback.input,
      output: fallback.output,
      class_name: fallback.class_name,
      input_label: fallback.input_label || "input",
      output_label: fallback.output_label || "output",
    };
    return {
      root: null,
      nodes: [fallbackNode],
      edges: [],
    };
  }

  const edges: AgentFlowEdge[] = [];
  const edgeKeys = new Set<string>();
  for (const raw of agentGraph.edges) {
    const caller = raw.caller.trim();
    const callee = raw.callee.trim();
    if (!caller || !callee || caller === callee) continue;
    if (caller === root || callee === root) continue;
    if (!paths.has(caller) || !paths.has(callee)) continue;
    const key = `${caller}::${callee}::${raw.type}`;
    if (edgeKeys.has(key)) continue;
    edgeKeys.add(key);
    edges.push({ ...raw, caller, callee, type: raw.type || "call" });
  }

  return { root, nodes: fixedNodes, edges };
}

function fallbackClassName(path: string, kind: AgentFlowNode["kind"]): string {
  const last = path.split(/[./]/).filter(Boolean).pop();
  return last || (kind === "composite" ? "Composite" : "Agent");
}

function graphSignature(agentGraph: AgentGraphResponse): string {
  return [
    agentGraph.root ?? "",
    agentGraph.nodes
      .map((node) => `${node.path}:${node.kind}:${node.parent_path ?? ""}:${node.class_name}`)
      .join("|"),
    agentGraph.edges.map((edge) => `${edge.caller}>${edge.callee}:${edge.type}`).join("|"),
  ].join("::");
}

function GraphCanvas({ agentGraph, runId }: AgentFlowGraphProps) {
  const selection = useUIStore((s) => s.graphSelection);
  const setSelection = useUIStore((s) => s.setGraphSelection);
  const clearSelection = useUIStore((s) => s.clearGraphSelection);
  const activeAgents = useActiveAgents(runId);

  const composites = useMemo(
    () => agentGraph.nodes.filter((n) => n.kind === "composite" && n.path !== agentGraph.root),
    [agentGraph.nodes, agentGraph.root],
  );

  // Default: every composite expanded so the first paint already shows the
  // full agent tree (matches the spec requirement "all visible, expandable").
  const [expanded, setExpanded] = useState<Set<string>>(
    () => new Set(composites.map((c) => c.path)),
  );

  // If new composites arrive after first paint (e.g. graph payload landed
  // a tick later), expand them by default but never undo manual collapses.
  const lastCompositeKey = useRef<string>("");
  useEffect(() => {
    const key = composites
      .map((c) => c.path)
      .sort()
      .join(",");
    if (key === lastCompositeKey.current) return;
    lastCompositeKey.current = key;
    setExpanded((prev) => {
      if (prev.size === 0 && composites.length > 0) {
        return new Set(composites.map((c) => c.path));
      }
      return prev;
    });
  }, [composites]);

  const toggleComposite = useCallback((path: string) => {
    setExpanded((curr) => {
      const next = new Set(curr);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    setExpanded(new Set(composites.map((c) => c.path)));
  }, [composites]);
  const collapseAll = useCallback(() => {
    setExpanded(new Set());
  }, []);

  const layout = useMemo(
    () =>
      layoutAgentFlow({
        nodes: agentGraph.nodes,
        edges: agentGraph.edges,
        rootPath: agentGraph.root,
        expanded,
      }),
    [agentGraph, expanded],
  );

  // Per-leaf invocation stats (latency / count). Use a stable `pathsKey` so
  // memos don't re-fire when the underlying array identity changes but the
  // path set is unchanged (the root cause of the React #185 loop).
  const visibleLeafPaths = useMemo(() => {
    const paths = layout.nodes.filter((n) => n.kind === "leaf" && !n.hidden).map((n) => n.path);
    return paths.sort();
  }, [layout.nodes]);
  const pathsKey = useMemo(() => visibleLeafPaths.join("|"), [visibleLeafPaths]);

  const invocationQueries = useQueries({
    queries: visibleLeafPaths.map((path) => ({
      queryKey: ["graph", "agent-invocations", runId, path] as const,
      queryFn: () => dashboardApi.agentInvocations(runId, path),
      staleTime: 30_000,
      retry: false,
    })),
  });

  const metaQueries = useQueries({
    queries: visibleLeafPaths.map((path) => ({
      queryKey: ["graph", "agent-meta", runId, path] as const,
      queryFn: () => dashboardApi.agentMeta(runId, path),
      staleTime: 60_000,
      retry: false,
    })),
  });

  // Content-based signatures so the stats memo only re-emits when actual
  // data changes, not on every render where `useQueries` returned a new
  // array reference for the same payload. This is the linchpin against
  // the React #185 max-update-depth loop the previous implementation hit.
  const invocationsSignature = invocationQueries
    .map((q) => {
      const inv = q.data?.invocations ?? [];
      return `${inv.length}/${inv[inv.length - 1]?.hash_content ?? ""}`;
    })
    .join(",");
  const metaSignature = metaQueries
    .map((q) => q.data?.trainable_paths.length ?? 0)
    .join(",");

  const statsByPath = useMemo(() => {
    const out: Record<
      string,
      { invocationCount: number; hashContent: string | null; trainable: boolean }
    > = {};
    visibleLeafPaths.forEach((path, i) => {
      const inv = invocationQueries[i]?.data;
      const meta = metaQueries[i]?.data;
      const rows = inv?.invocations ?? [];
      const last = rows[rows.length - 1] ?? null;
      out[path] = {
        invocationCount: rows.length,
        hashContent: last?.hash_content ?? null,
        trainable: meta?.trainable_paths ? meta.trainable_paths.length > 0 : false,
      };
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathsKey, invocationsSignature, metaSignature]);

  const childCounts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const n of agentGraph.nodes) {
      if (n.parent_path && n.parent_path !== agentGraph.root) {
        out[n.parent_path] = (out[n.parent_path] ?? 0) + 1;
      }
    }
    return out;
  }, [agentGraph]);

  const selectedAgentPath = selection?.kind === "edge" ? selection.agentPath : null;
  const activeAgentsKey = useMemo(
    () => Array.from(activeAgents).sort().join(","),
    [activeAgents],
  );

  const nodes: Node[] = useMemo(() => {
    return layout.nodes
      .filter((n) => !n.hidden)
      .map((n) => {
        const isComposite = n.kind === "composite";
        const sel = selectedAgentPath === n.path;
        const dimmed = selectedAgentPath != null && !sel;
        if (isComposite) {
          return {
            id: n.path,
            type: "composite",
            position: { x: n.x, y: n.y },
            style: { width: n.width, height: n.height },
            data: {
              path: n.path,
              className: n.className,
              expanded: n.expanded,
              selected: sel,
              dimmed,
              childCount: childCounts[n.path] ?? 0,
            },
          } satisfies Node;
        }
        const stats = statsByPath[n.path];
        return {
          id: n.path,
          type: "agent",
          position: { x: n.x, y: n.y },
          style: { width: n.width, height: n.height },
          data: {
            path: n.path,
            className: n.className,
            inputLabel: n.inputLabel,
            outputLabel: n.outputLabel,
            selected: sel,
            dimmed,
            active: activeAgents.has(n.path),
            trainable: stats?.trainable ?? false,
            hashContent: stats?.hashContent ?? null,
            invocationCount: stats?.invocationCount ?? 0,
          },
        } satisfies Node;
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout.nodes, selectedAgentPath, statsByPath, childCounts, activeAgentsKey]);

  // Filter and dedupe edges from layout.
  const visibleEdges = useMemo(() => {
    const seen = new Set<string>();
    const out: Array<{ caller: string; callee: string; type: string }> = [];
    for (const e of layout.edges) {
      if (!e.visible) continue;
      const key = `${e.caller}::${e.callee}::${e.type}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(e);
    }
    return out;
  }, [layout.edges]);

  const edges: Edge[] = useMemo(() => {
    return visibleEdges.map((e, i) => {
      const dimmed =
        selectedAgentPath != null &&
        selectedAgentPath !== e.caller &&
        selectedAgentPath !== e.callee;
      return {
        id: `${e.caller}-->${e.callee}-${e.type}-${i}`,
        source: e.caller,
        target: e.callee,
        type: "typed",
        data: {
          type: e.type,
          selected: false,
          dimmed,
          active: activeAgents.has(e.caller) && activeAgents.has(e.callee),
        },
      } satisfies Edge;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleEdges, selectedAgentPath, activeAgentsKey]);

  const onNodeClick = useCallback(
    (_evt: React.MouseEvent, node: Node) => {
      if (selectedAgentPath === node.id) clearSelection();
      else setSelection({ kind: "edge", agentPath: node.id });
    },
    [selectedAgentPath, clearSelection, setSelection],
  );

  const onNodeDoubleClick = useCallback(
    (_evt: React.MouseEvent, node: Node) => {
      if (node.type === "composite") {
        toggleComposite(node.id);
      }
    },
    [toggleComposite],
  );

  const copyMermaid = useCallback(async () => {
    try {
      const res = await dashboardApi.graph(runId);
      await navigator.clipboard.writeText(res.mermaid);
    } catch {
      // silent
    }
  }, [runId]);

  return (
    <div className="relative h-full w-full">
      <div className="absolute right-4 top-4 z-10 flex items-center gap-1 rounded-md border border-border bg-bg-1/95 p-1 shadow-[var(--shadow-card-soft)] backdrop-blur-md">
        <IconButton
          aria-label="expand all composites"
          onClick={expandAll}
          title="expand all composites"
          size="sm"
        >
          <Maximize2 size={13} />
        </IconButton>
        <IconButton
          aria-label="collapse all composites"
          onClick={collapseAll}
          title="collapse all composites"
          size="sm"
        >
          <Minimize2 size={13} />
        </IconButton>
        <span className="mx-0.5 h-4 w-px bg-border" />
        <Button size="sm" variant="ghost" onClick={copyMermaid} className="gap-1.5">
          <Copy size={12} />
          mermaid
        </Button>
      </div>
      <ReactFlow
        key={`${runId}-${nodes.map((node) => node.id).join("|")}-${edges
          .map((edge) => edge.id)
          .join("|")}`}
        nodes={nodes}
        edges={edges}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={FIT_VIEW_OPTIONS}
        panOnDrag
        zoomOnScroll
        minZoom={0.2}
        maxZoom={2.4}
        proOptions={{ hideAttribution: true }}
        onPaneClick={clearSelection}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="var(--color-border)" gap={24} />
        <MiniMap
          pannable
          zoomable
          maskColor="rgba(7, 9, 16, 0.65)"
          nodeColor="var(--color-bg-3)"
          nodeStrokeColor="var(--color-border)"
          nodeStrokeWidth={1}
          style={MINIMAP_STYLE}
        />
        <Controls
          showInteractive
          className="!rounded-md !border-border !bg-bg-1 [&>button]:!border-border [&>button]:!bg-bg-1 [&>button]:!text-muted hover:[&>button]:!bg-bg-3"
        />
      </ReactFlow>
    </div>
  );
}

function SingleLeafCanvas({ agentGraph, runId }: AgentFlowGraphProps) {
  const selection = useUIStore((s) => s.graphSelection);
  const setSelection = useUIStore((s) => s.setGraphSelection);
  const clearSelection = useUIStore((s) => s.clearGraphSelection);
  const activeAgents = useActiveAgents(runId);
  const autoSelectedRef = useRef(false);

  const single = agentGraph.nodes[0] ?? null;
  const singlePath = single?.path ?? "";

  const invocationQueries = useQueries({
    queries: [
      {
        queryKey: ["graph", "agent-invocations", runId, singlePath] as const,
        queryFn: () => dashboardApi.agentInvocations(runId, singlePath),
        staleTime: 30_000,
        retry: false as const,
        enabled: Boolean(singlePath),
      },
    ],
  });
  const metaQueries = useQueries({
    queries: [
      {
        queryKey: ["graph", "agent-meta", runId, singlePath] as const,
        queryFn: () => dashboardApi.agentMeta(runId, singlePath),
        staleTime: 60_000,
        retry: false as const,
        enabled: Boolean(singlePath),
      },
    ],
  });

  // Auto-select the leaf exactly once per mount; using a ref instead of a
  // useState flag avoids the rerender-after-setState that triggers the
  // React #185 max-update-depth loop.
  useEffect(() => {
    if (!singlePath || autoSelectedRef.current) return;
    autoSelectedRef.current = true;
    if (selection == null) {
      setSelection({ kind: "edge", agentPath: singlePath });
    }
  }, [singlePath, selection, setSelection]);

  const inv = invocationQueries[0]?.data;
  const meta = metaQueries[0]?.data;
  const invocationCount = inv?.invocations.length ?? 0;
  const lastHashContent = inv?.invocations[invocationCount - 1]?.hash_content ?? null;
  const trainable = meta?.trainable_paths ? meta.trainable_paths.length > 0 : false;
  const selectedSingle =
    selection?.kind === "edge" && selection.agentPath === singlePath && Boolean(singlePath);
  const activeAgentsKey = useMemo(
    () => Array.from(activeAgents).sort().join(","),
    [activeAgents],
  );

  const nodes: Node[] = useMemo(() => {
    if (!single) return [];
    return [
      {
        id: single.path,
        type: "agent",
        position: { x: 0, y: 0 },
        style: { width: 260, height: 76 },
        data: {
          path: single.path,
          className: single.class_name,
          inputLabel: single.input_label,
          outputLabel: single.output_label,
          selected: selectedSingle,
          dimmed: false,
          active: activeAgents.has(single.path),
          trainable,
          hashContent: lastHashContent,
          invocationCount,
        },
      } satisfies Node,
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    singlePath,
    selectedSingle,
    activeAgentsKey,
    trainable,
    lastHashContent,
    invocationCount,
  ]);

  const onNodeClick = useCallback(() => {
    if (selectedSingle) clearSelection();
    else if (singlePath) setSelection({ kind: "edge", agentPath: singlePath });
  }, [selectedSingle, clearSelection, setSelection, singlePath]);

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        key={`${runId}-${singlePath}`}
        nodes={nodes}
        edges={[]}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={SINGLE_FIT_VIEW_OPTIONS}
        panOnDrag
        zoomOnScroll
        minZoom={0.4}
        maxZoom={2.4}
        proOptions={{ hideAttribution: true }}
        onPaneClick={clearSelection}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="var(--color-border)" gap={24} />
        <Controls
          showInteractive
          className="!rounded-md !border-border !bg-bg-1 [&>button]:!border-border [&>button]:!bg-bg-1 [&>button]:!text-muted hover:[&>button]:!bg-bg-3"
        />
      </ReactFlow>
    </div>
  );
}

export function AgentFlowGraph({ agentGraph, runId }: AgentFlowGraphProps) {
  const normalizedGraph = useMemo(() => normalizeAgentGraph(agentGraph), [agentGraph]);
  const signature = useMemo(() => graphSignature(normalizedGraph), [normalizedGraph]);

  if (!normalizedGraph || normalizedGraph.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState title="waiting for first invocation" description="graph not ready yet" />
      </div>
    );
  }
  const [singleNode] = normalizedGraph.nodes;
  if (normalizedGraph.nodes.length === 1 && normalizedGraph.edges.length === 0 && singleNode) {
    // Re-key on the (run + path) so a different run gets a clean
    // ReactFlow instance instead of trying to diff into a stale store —
    // and make sure we never reuse internal state across runs.
    return (
      <ReactFlowProvider key={`single-${runId}-${signature}`}>
        <SingleLeafCanvas agentGraph={normalizedGraph} runId={runId} />
      </ReactFlowProvider>
    );
  }
  return (
    <ReactFlowProvider key={`group-${runId}-${signature}`}>
      <GraphCanvas agentGraph={normalizedGraph} runId={runId} />
    </ReactFlowProvider>
  );
}
