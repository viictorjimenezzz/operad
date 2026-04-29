import { AgentChrome } from "@/components/agent-view/page-shell/agent-chrome";
import type { AgentTabSpec } from "@/components/agent-view/page-shell/agent-tabs";
import { type BreadcrumbItem, Button, EmptyState } from "@/components/ui";
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

export function AgentRunDetailLayout() {
  const { runId, hashContent } = useParams<{ runId: string; hashContent: string }>();
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

  const latest = useMemo(() => {
    const rows = invocations.data?.invocations ?? [];
    return rows[rows.length - 1] ?? null;
  }, [invocations.data]);

  const rootAgentPath = summary.data?.root_agent_path ?? null;
  const meta = useAgentMeta(runId ?? null, rootAgentPath);
  const drift = useDrift(runId ?? null);
  const showDrift = (drift.data?.length ?? 0) > 0;

  const tabs = useMemo<AgentTabSpec[]>(() => {
    const next: AgentTabSpec[] = [
      { to: "", label: "Overview", end: true },
      { to: "/history", label: "History" },
      { to: "/metrics", label: "Metrics" },
    ];
    if (showDrift) next.push({ to: "/drift", label: "Drift" });
    return next;
  }, [showDrift]);

  const breadcrumbs = useMemo<BreadcrumbItem[]>(() => {
    if (hashContent && summary.data) {
      const className = summary.data.root_agent_path?.split(".").at(-1) ?? "Agent";
      return [
        { label: "Agents", to: "/agents" },
        { label: className, to: `/agents/${hashContent}` },
      ];
    }
    return [{ label: "Agents", to: "/agents" }];
  }, [hashContent, summary.data]);

  if (!runId) return <EmptyState title="missing run id" />;
  if (summary.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted">
        loading run...
      </div>
    );
  }
  if (summary.error || !summary.data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <EmptyState
          title="run not found"
          description="the dashboard does not have this run in its registry"
          cta={
            <Link to="/agents">
              <Button variant="primary" size="sm">
                back to agents
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  const run = summary.data;
  const resolvedHash = hashContent ?? latest?.hash_content ?? meta.data?.hash_content ?? null;
  const basePath = resolvedHash
    ? `/agents/${resolvedHash}/runs/${runId}`
    : `/agents/${hashContent ?? ""}/runs/${runId}`;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <AgentChrome run={run} basePath={basePath} tabs={tabs} breadcrumbs={breadcrumbs} />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
