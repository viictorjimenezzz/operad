import { DriftBlock } from "@/components/agent-view/overview/drift-block";
import { EmptyState } from "@/components/ui";
import { useDrift, useRunInvocations } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function SingleInvocationDriftTab() {
  const { runId } = useParams<{ runId: string }>();
  const drift = useDrift(runId);
  const invocations = useRunInvocations(runId);

  if (!runId) return null;
  if ((drift.data?.length ?? 0) === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="no drift events"
          description="the route is hidden until prompt drift exists for this invocation"
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-[1100px]">
        <DriftBlock dataInvocations={invocations.data} runId={runId} />
      </div>
    </div>
  );
}
