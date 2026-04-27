import { AgentFlowGraph } from "@/components/agent-view/graph/agent-flow-graph";
import { InspectorShell } from "@/components/agent-view/graph/inspector/inspector-shell";
import { SplitPane } from "@/components/agent-view/graph/split-pane";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { dashboardApi } from "@/lib/api/dashboard";
import type { AgentGraphResponse, IoGraphResponse } from "@/lib/types";
import { useUIStore } from "@/stores";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

export function GraphPage({ runId }: { runId: string }) {
  const agentGraphQuery = useQuery({
    queryKey: ["run", "agent_graph", runId] as const,
    queryFn: () => dashboardApi.runAgentGraph(runId),
  });
  const selection = useUIStore((s) => s.graphSelection);
  const clearSelection = useUIStore((s) => s.clearGraphSelection);

  // Adapt the agent_graph into the legacy IoGraphResponse shape so the
  // existing InspectorShell (which keys off `e.agent_path`) keeps working
  // without a parallel rewrite of every inspector tab.
  const ioGraphAdapter: IoGraphResponse | null = useMemo(() => {
    if (!agentGraphQuery.data) return null;
    return adaptAgentGraphForInspector(agentGraphQuery.data);
  }, [agentGraphQuery.data]);

  if (agentGraphQuery.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted">
        loading graph…
      </div>
    );
  }
  if (agentGraphQuery.error || !agentGraphQuery.data || !ioGraphAdapter) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="graph unavailable"
          description="this run has not produced an agent_graph payload"
          cta={
            <Button size="sm" onClick={() => agentGraphQuery.refetch()}>
              retry
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <SplitPane
      open={selection !== null}
      left={<AgentFlowGraph agentGraph={agentGraphQuery.data} runId={runId} />}
      right={
        <InspectorShell runId={runId} ioGraph={ioGraphAdapter} onClose={clearSelection} />
      }
    />
  );
}

function adaptAgentGraphForInspector(ag: AgentGraphResponse): IoGraphResponse {
  return {
    root: ag.root,
    nodes: [],
    edges: ag.nodes
      .filter((n) => n.path !== ag.root)
      .map((n) => ({
        agent_path: n.path,
        class_name: n.class_name,
        kind: n.kind,
        from: n.input,
        to: n.output,
        composite_path: n.parent_path,
      })),
    composites: [],
  };
}
