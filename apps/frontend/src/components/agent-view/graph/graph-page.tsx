import { InspectorShell } from "@/components/agent-view/graph/inspector/inspector-shell";
import { InteractiveGraph } from "@/components/agent-view/graph/interactive-graph";
import { SplitPane } from "@/components/agent-view/graph/split-pane";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { dashboardApi } from "@/lib/api/dashboard";
import { useUIStore } from "@/stores";
import { useQuery } from "@tanstack/react-query";

export function GraphPage({ runId }: { runId: string }) {
  const ioGraphQuery = useQuery({
    queryKey: ["run", "io_graph", runId] as const,
    queryFn: () => dashboardApi.runIoGraph(runId),
  });
  const selection = useUIStore((s) => s.graphSelection);
  const clearSelection = useUIStore((s) => s.clearGraphSelection);

  if (ioGraphQuery.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted">
        loading graph…
      </div>
    );
  }
  if (ioGraphQuery.error || !ioGraphQuery.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="graph unavailable"
          description="this run has not produced an io_graph payload"
          cta={
            <Button size="sm" onClick={() => ioGraphQuery.refetch()}>
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
      left={<InteractiveGraph ioGraph={ioGraphQuery.data} runId={runId} />}
      right={<InspectorShell runId={runId} ioGraph={ioGraphQuery.data} onClose={clearSelection} />}
    />
  );
}
