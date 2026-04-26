import { DashboardRenderer } from "@/components/DashboardRenderer";
import { useArchivedRun, useRestoreArchivedRun } from "@/hooks/use-runs";
import { pickLayout } from "@/layouts";
import { truncateMiddle } from "@/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { useEventBufferStore } from "@/stores";
import { useRunStore } from "@/stores/run";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

export function ArchivedRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const archived = useArchivedRun(runId);
  const restore = useRestoreArchivedRun();
  const setCurrentRun = useRunStore((s) => s.setCurrentRun);
  const ingest = useEventBufferStore((s) => s.ingest);
  const clear = useEventBufferStore((s) => s.clear);

  useEffect(() => {
    setCurrentRun(runId ?? null);
    return () => setCurrentRun(null);
  }, [runId, setCurrentRun]);

  useEffect(() => {
    if (!runId || !archived.data) return;
    clear(runId);
    for (const env of archived.data.events) ingest(env);
  }, [archived.data, clear, ingest, runId]);

  if (!runId) return <EmptyState title="missing run id" />;
  if (archived.isLoading) return <div className="p-6 text-xs text-muted">loading archived run…</div>;
  if (archived.error || !archived.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="archived run not found"
          description="this run is not available in the archive store"
          cta={
            <Link to="/archive">
              <Button variant="primary" size="sm">
                back to archive
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  const summary = archived.data.summary;
  const layout = pickLayout(summary.algorithm_path);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border bg-bg-1 px-4 py-2 text-xs">
        <Link to="/archive" className="text-muted hover:text-text">
          ← archive
        </Link>
        <span className="text-muted">/</span>
        <span className="font-mono text-text">{truncateMiddle(runId, 20)}</span>
        <Badge
          variant={
            summary.state === "running"
              ? "live"
              : summary.state === "error"
                ? "error"
                : "ended"
          }
        >
          {summary.state}
        </Badge>
        {summary.algorithm_path ? <Badge variant="algo">{summary.algorithm_path}</Badge> : null}
        <div className="ml-auto flex items-center gap-2">
          <span className="font-mono text-muted">layout · {layout.algorithm}</span>
          <Button
            size="sm"
            variant="primary"
            disabled={restore.isPending}
            onClick={async () => {
              await restore.mutateAsync(runId);
              navigate(`/runs/${runId}`);
            }}
          >
            Restore to live
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3">
        <DashboardRenderer
          layout={layout}
          context={{ runId, algorithmPath: summary.algorithm_path ?? "" }}
        />
      </div>
    </div>
  );
}
