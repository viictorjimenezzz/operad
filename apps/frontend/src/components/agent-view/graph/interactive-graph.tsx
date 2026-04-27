import { AgentEdgeCard } from "@/components/agent-view/graph/agent-edge-card";
import {
  type CompositeGroup,
  applyCompositeCollapse,
  deriveCompositeGroups,
  toggleComposite,
} from "@/components/agent-view/graph/composite-grouping";
import { IoTypeCard } from "@/components/agent-view/graph/io-type-card";
import { applyDagreLayout } from "@/components/agent-view/graph/layout";
import { useActiveAgents } from "@/components/agent-view/graph/use-active-agents";
import { Button, EmptyState, IconButton } from "@/components/ui";
import { dashboardApi } from "@/lib/api/dashboard";
import type { IoGraphResponse } from "@/lib/types";
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
import { useCallback, useMemo, useState } from "react";

interface InteractiveGraphProps {
  ioGraph: IoGraphResponse | null | undefined;
  runId: string;
}

const nodeTypes = { ioType: IoTypeCard };
const edgeTypes = { agentEdge: AgentEdgeCard };

function GraphCanvas({ ioGraph, runId }: InteractiveGraphProps) {
  const selection = useUIStore((s) => s.graphSelection);
  const setSelection = useUIStore((s) => s.setGraphSelection);
  const clearSelection = useUIStore((s) => s.clearGraphSelection);
  const activeAgents = useActiveAgents(runId);

  const allGroups = useMemo(
    () =>
      deriveCompositeGroups(
        ioGraph ?? { root: null, nodes: [], edges: [], composites: [] },
      ),
    [ioGraph],
  );
  const [groupState, setGroupState] = useState<CompositeGroup[]>(() => allGroups);

  // Re-derive when graph payload changes (preserves user's collapse choices when paths overlap).
  useMemo(() => {
    setGroupState((curr) => {
      const next: CompositeGroup[] = [];
      for (const fresh of allGroups) {
        const existing = curr.find((g) => g.path === fresh.path);
        next.push(existing ? { ...fresh, collapsed: existing.collapsed } : fresh);
      }
      return next;
    });
  }, [allGroups]);

  const source = useMemo(() => {
    const graph = ioGraph ?? { root: null, nodes: [], edges: [], composites: [] };
    return groupState.length === 0 ? graph : applyCompositeCollapse(graph, groupState);
  }, [groupState, ioGraph]);

  const toggleCompositeAt = useCallback((path: string) => {
    setGroupState((curr) => toggleComposite(curr, path));
  }, []);

  // Per-edge invocation stats (latency / tokens / count).
  const edgeStatsQueries = useQueries({
    queries: source.edges.map((e) => ({
      queryKey: ["graph", "edge-invocations", runId, e.agent_path] as const,
      queryFn: () => dashboardApi.agentInvocations(runId, e.agent_path),
      enabled: e.kind === "leaf",
      staleTime: 30_000,
      retry: false,
    })),
  });

  const edgeMetaQueries = useQueries({
    queries: source.edges.map((e) => ({
      queryKey: ["graph", "edge-meta", runId, e.agent_path] as const,
      queryFn: () => dashboardApi.agentMeta(runId, e.agent_path),
      staleTime: 60_000,
      retry: false,
    })),
  });

  const edgeStats = useMemo(() => {
    return source.edges.map((e, i) => {
      const inv = edgeStatsQueries[i]?.data;
      const meta = edgeMetaQueries[i]?.data;
      const rows = inv?.invocations ?? [];
      const latencies = rows.map((r) => r.latency_ms).filter((x): x is number => x != null);
      const totalTokens = rows.reduce(
        (acc, r) => acc + (r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0),
        0,
      );
      const last = rows[rows.length - 1] ?? null;
      return {
        agentPath: e.agent_path,
        latencyMs:
          latencies.length > 0 ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null,
        tokens: rows.length > 0 ? totalTokens : null,
        invocationCount: rows.length,
        cassette: rows.some(
          (r) => r.script === "cassette" || (r as Record<string, unknown>).cassette === true,
        ),
        hashContent: last?.hash_content ?? null,
        trainable: meta?.trainable_paths ? meta.trainable_paths.length > 0 : false,
        hookOverride: Boolean(meta?.forward_in_overridden ?? meta?.forward_out_overridden),
      };
    });
  }, [source.edges, edgeStatsQueries, edgeMetaQueries]);

  const fieldCounts = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const node of source.nodes) acc[node.key] = node.fields.length;
    return acc;
  }, [source.nodes]);

  const edges: Edge[] = useMemo(() => {
    const activeEdgePath = selection?.kind === "edge" ? selection.agentPath : null;
    return source.edges.map((edge, i) => {
      const stats = edgeStats[i];
      const dimmed = Boolean(activeEdgePath && activeEdgePath !== edge.agent_path);
      const selected = activeEdgePath === edge.agent_path;
      const compositePath = edge.kind === "composite" ? edge.composite_path : null;
      const compositeGroup =
        compositePath != null
          ? groupState.find((g) => g.path === compositePath) ?? null
          : null;
      return {
        id: edge.agent_path,
        source: edge.from,
        target: edge.to,
        type: "agentEdge",
        data: {
          agentPath: edge.agent_path,
          className: edge.class_name,
          classKind: edge.kind,
          selected,
          dimmed,
          active: activeAgents.has(edge.agent_path),
          trainable: stats?.trainable ?? false,
          hookOverride: stats?.hookOverride ?? false,
          cassette: stats?.cassette ?? false,
          hashContent: stats?.hashContent ?? null,
          latencyMs: stats?.latencyMs ?? null,
          tokens: stats?.tokens ?? null,
          invocationCount: stats?.invocationCount ?? 0,
          expanded: compositeGroup ? !compositeGroup.collapsed : undefined,
          onToggleExpand: compositePath
            ? () => toggleCompositeAt(compositePath)
            : undefined,
          onSelect: () => {
            if (selection?.kind === "edge" && selection.agentPath === edge.agent_path) {
              clearSelection();
            } else {
              setSelection({ kind: "edge", agentPath: edge.agent_path });
            }
          },
        },
      } satisfies Edge;
    });
  }, [
    source.edges,
    edgeStats,
    selection,
    activeAgents,
    setSelection,
    clearSelection,
    groupState,
    toggleCompositeAt,
  ]);

  const nodes: Node[] = useMemo(() => {
    const activeEdgePath = selection?.kind === "edge" ? selection.agentPath : null;

    const graphNodes: Node[] = source.nodes.map((node) => {
      const selected = selection?.kind === "node" && selection.nodeKey === node.key;
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
          selected,
          dimmed,
          onSelect: () => {
            if (selection?.kind === "node" && selection.nodeKey === node.key) {
              clearSelection();
            } else {
              setSelection({ kind: "node", nodeKey: node.key });
            }
          },
        },
      };
    });

    return applyDagreLayout(graphNodes, edges, { fieldCounts });
  }, [source, selection, fieldCounts, edges, clearSelection, setSelection]);

  const expandAll = useCallback(() => {
    setGroupState((curr) => curr.map((g) => ({ ...g, collapsed: false })));
  }, []);
  const collapseAll = useCallback(() => {
    setGroupState((curr) => curr.map((g) => ({ ...g, collapsed: true })));
  }, []);

  const copyMermaid = useCallback(async () => {
    try {
      const res = await dashboardApi.graph(runId);
      await navigator.clipboard.writeText(res.mermaid);
    } catch {
      // silent — toolbar button stays inert if backend errors
    }
  }, [runId]);

  return (
    <div className="relative h-full w-full">
      <div className="absolute right-4 top-4 z-10 flex items-center gap-1.5 rounded-lg border border-border bg-bg-1/95 p-1 shadow-[var(--shadow-card-soft)] backdrop-blur-md">
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
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.18, duration: 220 }}
        panOnDrag
        zoomOnScroll
        minZoom={0.2}
        maxZoom={2.4}
        proOptions={{ hideAttribution: true }}
        onPaneClick={() => clearSelection()}
      >
        <Background color="var(--color-border)" gap={24} />
        <MiniMap
          pannable
          zoomable
          maskColor="rgba(7, 9, 16, 0.65)"
          nodeColor={() => "var(--color-bg-3)"}
          nodeStrokeColor={() => "var(--color-border)"}
          nodeStrokeWidth={1}
          style={{
            background: "var(--color-bg-1)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
          }}
        />
        <Controls
          showInteractive
          className="!rounded-lg !border-border !bg-bg-1 [&>button]:!border-border [&>button]:!bg-bg-1 [&>button]:!text-muted hover:[&>button]:!bg-bg-3"
        />
      </ReactFlow>
    </div>
  );
}

export function InteractiveGraph({ ioGraph, runId }: InteractiveGraphProps) {
  if (!ioGraph || ioGraph.edges.length === 0 || ioGraph.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState title="waiting for first invocation" description="graph not ready yet" />
      </div>
    );
  }
  return (
    <ReactFlowProvider>
      <GraphCanvas ioGraph={ioGraph} runId={runId} />
    </ReactFlowProvider>
  );
}
