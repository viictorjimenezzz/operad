import { AgentChrome } from "@/components/agent-view/page-shell/agent-chrome";
import type { AgentTabSpec } from "@/components/agent-view/page-shell/agent-tabs";
import { Breadcrumb, Button, EmptyState, type BreadcrumbItem } from "@/components/ui";
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
import { Link, Outlet, useLocation, useParams } from "react-router-dom";

/**
 * The single-invocation page. Shared by:
 *   /runs/:runId
 *   /agents/:hashContent/runs/:runId
 *   /algorithms/:runId
 *   /training/:runId
 *
 * The breadcrumb adapts based on which route hit us.
 */
export function RunDetailLayout() {
  const params = useParams<{ runId: string; hashContent?: string }>();
  const runId = params.runId;
  const hashContent = params.hashContent ?? null;

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

  const location = useLocation();
  const path = location.pathname;
  const isAlgorithm = path.startsWith("/algorithms/");
  const isTraining = path.startsWith("/training/");

  const basePath = useMemo(() => {
    if (isAlgorithm) return `/algorithms/${runId}`;
    if (isTraining) return `/training/${runId}`;
    if (hashContent) return `/agents/${hashContent}/runs/${runId}`;
    return `/runs/${runId}`;
  }, [hashContent, runId, isAlgorithm, isTraining]);

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
    if (showTrain || isTraining) base.push({ to: "/train", label: "Train" });
    if (showDrift) base.push({ to: "/drift", label: "Drift" });
    return base;
  }, [invocationCount, showTrain, showDrift, isTraining]);

  const breadcrumbs = useMemo<BreadcrumbItem[]>(() => {
    if (isAlgorithm) {
      return [{ label: "Algorithms", to: "/algorithms" }];
    }
    if (isTraining) {
      return [{ label: "Training", to: "/training" }];
    }
    if (hashContent && summary.data) {
      const className = summary.data.root_agent_path?.split(".").at(-1) ?? "Agent";
      return [
        { label: "Agents", to: "/agents" },
        { label: className, to: `/agents/${hashContent}` },
      ];
    }
    return [{ label: "Runs", to: "/agents" }];
  }, [isAlgorithm, isTraining, hashContent, summary.data]);

  if (!runId) return <EmptyState title="missing run id" />;
  if (summary.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted">loading run…</div>
    );
  }
  if (summary.error || !summary.data) {
    return (
      <div className="flex h-full flex-col">
        <Breadcrumb items={[{ label: "Run not found" }]} />
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
      </div>
    );
  }

  const run = summary.data;
  const langfuseUrl = latest?.langfuse_url ?? null;
  const hashContentResolved = hashContent ?? latest?.hash_content ?? null;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <AgentChrome
        run={run}
        langfuseUrl={langfuseUrl}
        hashContent={hashContentResolved}
        basePath={basePath}
        tabs={tabs}
        breadcrumbs={breadcrumbs}
      />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
