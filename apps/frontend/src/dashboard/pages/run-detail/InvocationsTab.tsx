import { InvocationsList } from "@/components/agent-view/overview/invocations-list";
import { EmptyState } from "@/components/ui/empty-state";
import { useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function InvocationsTab() {
  const { runId } = useParams<{ runId: string }>();
  const summary = useRunSummary(runId);
  const invocations = useRunInvocations(runId);

  if (!runId) return null;

  return (
    <div className="h-full overflow-auto px-6 py-6">
      <div className="mx-auto max-w-[1100px]">
        {invocations.isLoading || summary.isLoading ? (
          <div className="text-xs text-muted">loading invocations…</div>
        ) : !invocations.data || invocations.data.invocations.length === 0 ? (
          <EmptyState
            title="no invocations yet"
            description="this run has not received its first invocation"
          />
        ) : (
          <InvocationsList
            runId={runId}
            invocations={invocations.data.invocations}
            agentPath={invocations.data.agent_path ?? summary.data?.root_agent_path ?? ""}
            initiallyExpandedId={
              invocations.data.invocations[invocations.data.invocations.length - 1]?.id ?? null
            }
            density="full"
          />
        )}
      </div>
    </div>
  );
}
