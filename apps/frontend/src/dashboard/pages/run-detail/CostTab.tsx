import { CostLatencyBlock } from "@/components/agent-view/overview/cost-latency-block";
import { EmptyState } from "@/components/ui";
import { useRunInvocations } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function CostTab() {
  const { runId } = useParams<{ runId: string }>();
  const invocations = useRunInvocations(runId);

  if (!runId) return null;

  return (
    <div className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-[1100px] space-y-3">
        {invocations.data && invocations.data.invocations.length === 0 ? (
          <EmptyState
            title="no cost data yet"
            description="cost & latency are computed once the agent has run at least once"
          />
        ) : (
          <CostLatencyBlock dataInvocations={invocations.data} />
        )}
      </div>
    </div>
  );
}
