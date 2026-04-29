import { GraphPage } from "@/components/agent-view/graph/graph-page";
import { EmptyState } from "@/components/ui";
import { useAgentGroup } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function AgentGroupGraphTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const runs = group.data?.runs ?? [];
  const newestRuns = [...runs].sort((a, b) => b.started_at - a.started_at);
  const latestGraphRun = newestRuns.find((run) => run.has_graph) ?? newestRuns[0] ?? null;

  if (!hashContent) return null;
  if (!latestGraphRun) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="graph unavailable"
          description="this group has no invocation to graph yet"
        />
      </div>
    );
  }
  return <GraphPage runId={latestGraphRun.run_id} />;
}
