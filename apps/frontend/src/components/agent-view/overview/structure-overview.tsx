import { AgentFlowGraph } from "@/components/agent-view/graph/agent-flow-graph";
import { dashboardApi } from "@/lib/api/dashboard";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

export function StructureOverview({
  runId,
  hashContent,
}: {
  runId: string;
  hashContent: string | null;
}) {
  const query = useQuery({
    queryKey: ["run", "agent_graph", runId] as const,
    queryFn: () => dashboardApi.runAgentGraph(runId),
    staleTime: 60_000,
  });

  if (!query.data || query.data.nodes.length <= 1) return null;

  return (
    <section className="border-t border-border pt-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
          structure
        </span>
        {hashContent ? (
          <Link
            to={`/agents/${hashContent}/graph`}
            className="text-[12px] text-accent hover:text-accent-strong"
          >
            open graph
          </Link>
        ) : null}
      </div>
      <div
        className="overflow-hidden rounded-md border border-border"
        style={{ height: 280 }}
      >
        <AgentFlowGraph agentGraph={query.data} runId={runId} />
      </div>
    </section>
  );
}
