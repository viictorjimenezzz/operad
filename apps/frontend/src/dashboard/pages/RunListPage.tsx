import { useRuns } from "@/hooks/use-runs";
import { formatDurationMs, formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { useStreamStore } from "@/stores/stream";
import { Link } from "react-router-dom";

export function RunListPage() {
  const { data: runs, isLoading } = useRuns();
  const status = useStreamStore((s) => s.status);

  if (isLoading) {
    return <div className="p-6 text-xs text-muted">loading runs…</div>;
  }
  if (!runs || runs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="no runs yet"
          description={
            <>
              start a demo: <code className="rounded bg-bg-2 px-1 py-0.5 font-mono">make demo</code>{" "}
              or attach from your own code via{" "}
              <code className="rounded bg-bg-2 px-1 py-0.5 font-mono">
                operad.dashboard.attach()
              </code>
              .
              {status !== "live" && status !== "idle" && (
                <span className="block pt-2 text-warn">stream is {status}</span>
              )}
            </>
          }
        />
      </div>
    );
  }

  return (
    <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {runs.map((run) => (
        <Link key={run.run_id} to={`/runs/${run.run_id}`} className="contents">
          <Card className="cursor-pointer transition-colors hover:border-border-strong">
            <CardHeader>
              <CardTitle className="font-mono normal-case tracking-normal text-text">
                {truncateMiddle(run.run_id, 18)}
              </CardTitle>
              <Badge
                variant={
                  run.state === "running" ? "live" : run.state === "error" ? "error" : "ended"
                }
              >
                {run.state}
              </Badge>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
                <dt className="text-muted">algorithm</dt>
                <dd className="m-0 truncate font-mono text-text">
                  {run.algorithm_path ?? <span className="text-muted-2">—</span>}
                </dd>
                <dt className="text-muted">root</dt>
                <dd className="m-0 truncate font-mono text-text">
                  {run.root_agent_path ?? <span className="text-muted-2">—</span>}
                </dd>
                <dt className="text-muted">events</dt>
                <dd className="m-0 tabular-nums">{run.event_total}</dd>
                <dt className="text-muted">duration</dt>
                <dd className="m-0 tabular-nums">
                  {run.duration_ms > 0
                    ? formatDurationMs(run.duration_ms)
                    : formatRelativeTime(run.started_at)}
                </dd>
              </dl>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
