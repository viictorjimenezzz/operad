import { MetricsValueTable } from "@/components/agent-view/overview/metrics-value-table";
import { EmptyState } from "@/components/ui";
import { useRunSummary } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function SingleInvocationMetricsTab() {
  const { runId, hashContent } = useParams<{ runId: string; hashContent: string }>();
  const summary = useRunSummary(runId);

  if (!runId) return null;
  if (summary.isLoading) {
    return <div className="p-4 text-xs text-muted">loading metrics...</div>;
  }
  if (!summary.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState title="metrics unavailable" description="the run summary has not loaded" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto max-w-[980px]">
        <MetricsValueTable dataSummary={summary.data} runId={runId} hashContent={hashContent} />
      </div>
    </div>
  );
}
