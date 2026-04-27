import { AgentChrome } from "@/components/agent-view/page-shell/agent-chrome";
import type { AgentTabSpec } from "@/components/agent-view/page-shell/agent-tabs";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  useAgentMeta,
  useDrift,
  useRunEvents,
  useRunInvocations,
  useRunSummary,
} from "@/hooks/use-runs";
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

  const rootAgentPath = summary.data?.root_agent_path ?? null;
  const meta = useAgentMeta(runId ?? null, rootAgentPath);
  const drift = useDrift(runId ?? null);

  const showTrain = (meta.data?.trainable_paths?.length ?? 0) > 0;
  const showDrift = (drift.data?.length ?? 0) > 0;

  const tabs = useMemo<AgentTabSpec[]>(() => {
    const base: AgentTabSpec[] = [
      { to: "", label: "Overview", end: true },
      { to: "/graph", label: "Graph" },
      {
        to: "/invocations",
        label: "Invocations",
        badge: invocationCount > 0 ? invocationCount : undefined,
      },
      { to: "/cost", label: "Cost" },
    ];
    if (showTrain) base.push({ to: "/train", label: "Train" });
    if (showDrift) base.push({ to: "/drift", label: "Drift" });
    return base;
  }, [invocationCount, showTrain, showDrift]);

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
      <AgentChrome
        run={run}
        langfuseUrl={langfuseUrl}
        hashContent={hashContent}
        basePath={`/runs/${runId}`}
        tabs={tabs}
      />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
