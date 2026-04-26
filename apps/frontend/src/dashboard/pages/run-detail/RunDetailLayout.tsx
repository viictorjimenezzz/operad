import { AgentHero } from "@/components/agent-view/page-shell/agent-hero";
import { AgentTabs } from "@/components/agent-view/page-shell/agent-tabs";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useRunEvents, useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { useEventBufferStore } from "@/stores";
import { useRunStore } from "@/stores/run";
import { useEffect, useMemo } from "react";
import { Link, Outlet, useParams } from "react-router-dom";

export function RunDetailLayout() {
  const { runId } = useParams<{ runId: string }>();
  const setCurrentRun = useRunStore((s) => s.setCurrentRun);
  const summary = useRunSummary(runId);
  const events = useRunEvents(runId);
  const invocations = useRunInvocations(runId);
  const ingest = useEventBufferStore((s) => s.ingest);

  useEffect(() => {
    setCurrentRun(runId ?? null);
    return () => setCurrentRun(null);
  }, [runId, setCurrentRun]);

  useEffect(() => {
    if (!events.data) return;
    for (const env of events.data.events) ingest(env);
  }, [events.data, ingest]);

  const invocationCount = invocations.data?.invocations.length ?? 0;
  const latest = useMemo(() => {
    const rows = invocations.data?.invocations ?? [];
    return rows[rows.length - 1] ?? null;
  }, [invocations.data]);

  if (!runId) return <EmptyState title="missing run id" />;
  if (summary.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted">loading run…</div>
    );
  }
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

  const run = summary.data;
  const langfuseUrl = latest?.langfuse_url ?? null;
  const hashContent = latest?.hash_content ?? null;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-border bg-bg px-4 py-1.5 text-[12px]">
        <Link to="/" className="text-muted-2 transition-colors hover:text-text">
          runs
        </Link>
        <span className="text-muted-2" aria-hidden>
          /
        </span>
        <span className="font-mono text-muted">{run.run_id.slice(0, 12)}…</span>
      </div>
      <AgentHero run={run} langfuseUrl={langfuseUrl} hashContent={hashContent} />
      <AgentTabs
        base={`/runs/${runId}`}
        tabs={[
          { to: "", label: "Overview", end: true },
          { to: "/graph", label: "Graph" },
          {
            to: "/invocations",
            label: "Invocations",
            badge: invocationCount > 0 ? invocationCount : undefined,
          },
        ]}
      />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
