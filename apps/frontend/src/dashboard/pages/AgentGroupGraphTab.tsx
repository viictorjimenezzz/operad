import { GraphPage } from "@/components/agent-view/graph/graph-page";
import { EmptyState } from "@/components/ui";
import { useAgentGroup } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function AgentGroupGraphTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const latestRun = group.data?.runs.at(-1) ?? null;

  if (!hashContent) return null;
  if (!latestRun) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="graph unavailable"
          description="this group has no invocation to graph yet"
        />
      </div>
    );
  }
  return <GraphPage runId={latestRun.run_id} />;
}
