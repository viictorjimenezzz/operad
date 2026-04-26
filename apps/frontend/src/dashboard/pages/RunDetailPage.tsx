import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useRunEvents, useRunSummary } from "@/hooks/use-runs";
import { pickLayout } from "@/layouts";
import { truncateMiddle } from "@/lib/utils";
import { useEventBufferStore } from "@/stores";
import { useRunStore } from "@/stores/run";
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const setCurrentRun = useRunStore((s) => s.setCurrentRun);
  const summary = useRunSummary(runId);
  const events = useRunEvents(runId);
  const ingest = useEventBufferStore((s) => s.ingest);

  useEffect(() => {
    setCurrentRun(runId ?? null);
    return () => setCurrentRun(null);
  }, [runId, setCurrentRun]);

  // Seed the event buffer with the historic snapshot the moment the
  // run-detail mounts; the live /stream subscription appends from
  // there onwards.
  useEffect(() => {
    if (!events.data) return;
    for (const env of events.data.events) ingest(env);
  }, [events.data, ingest]);

  if (!runId) return <EmptyState title="missing run id" />;
  if (summary.isLoading) return <div className="p-6 text-xs text-muted">loading run…</div>;
  if (summary.error || !summary.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="run not found"
          description="the dashboard does not have this run in its registry"
          cta={
            <Link to="/">
              <Button variant="primary" size="sm">
                back to runs
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  const layout = pickLayout(summary.data.algorithm_path);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border bg-bg-1 px-4 py-2 text-xs">
        <Link to="/" className="text-muted hover:text-text">
          ← runs
        </Link>
        <span className="text-muted">/</span>
        <span className="font-mono text-text">{truncateMiddle(runId, 20)}</span>
        <Badge
          variant={
            summary.data.state === "running"
              ? "live"
              : summary.data.state === "error"
                ? "error"
                : "ended"
          }
        >
          {summary.data.state}
        </Badge>
        {summary.data.algorithm_path ? (
          <Badge variant="algo">{summary.data.algorithm_path}</Badge>
        ) : null}
        <span className="ml-auto font-mono text-muted">layout · {layout.algorithm}</span>
      </div>
      <div className="flex-1 overflow-auto p-3">
        <DashboardRenderer
          layout={layout}
          context={{ runId, algorithmPath: summary.data.algorithm_path ?? "" }}
        />
      </div>
    </div>
  );
}
