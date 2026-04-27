import { DriftBlock } from "@/components/agent-view/overview/drift-block";
import { EmptyState } from "@/components/ui";
import { useRunInvocations } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function DriftTab() {
  const { runId } = useParams<{ runId: string }>();
  const invocations = useRunInvocations(runId);

  if (!runId) return null;

  return (
    <div className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-[1100px] space-y-3">
        {invocations.data && invocations.data.invocations.length < 2 ? (
          <EmptyState
            title="drift needs 2+ invocations"
            description="prompt drift is computed by comparing prompts across invocations"
          />
        ) : (
          <DriftBlock dataInvocations={invocations.data} runId={runId} />
        )}
      </div>
    </div>
  );
}
