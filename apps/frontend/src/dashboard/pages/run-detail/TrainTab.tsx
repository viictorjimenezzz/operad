import { TrainableParamsBlock } from "@/components/agent-view/overview/trainable-params-block";
import { EmptyState } from "@/components/ui";
import { useRunSummary } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function TrainTab() {
  const { runId } = useParams<{ runId: string }>();
  const summary = useRunSummary(runId);

  if (!runId) return null;

  return (
    <div className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-[1100px] space-y-3">
        {!summary.data?.root_agent_path ? (
          <EmptyState
            title="no agent metadata yet"
            description="trainable parameters are exposed once the agent has been built"
          />
        ) : (
          <TrainableParamsBlock dataSummary={summary.data} runId={runId} defaultOpen />
        )}
      </div>
    </div>
  );
}
