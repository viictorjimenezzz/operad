import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import {
  Breadcrumb,
  type BreadcrumbItem,
  EmptyState,
  HashTag,
  Metric,
  Pill,
} from "@/components/ui";
import { useRunEvents, useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { resolveLayout } from "@/layouts";
import type { RunSummary } from "@/lib/types";
import {
  formatCostOrUnavailable,
  formatTokenPairOrUnavailable,
  formatTokensOrUnavailable,
  hasTokenUsage,
} from "@/lib/usage";
import { formatDurationMs, formatRelativeTime } from "@/lib/utils";
import { useEventBufferStore } from "@/stores";
import { useRunStore } from "@/stores/run";
import { ExternalLink } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useLocation, useParams } from "react-router-dom";

export function AlgorithmDetailLayout() {
  const { runId } = useParams<{ runId: string }>();
  const location = useLocation();
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
      <EmptyState
        title="run not found"
        description="the dashboard does not have this run in its registry"
      />
    );
  }

  const run = summary.data;
  const layout = resolveLayout(run.algorithm_path);
  const isOpro = location.pathname.startsWith("/opro/");
  const breadcrumbs: BreadcrumbItem[] = isOpro
    ? [{ label: "OPRO", to: "/opro" }]
    : [{ label: "Algorithms", to: "/algorithms" }];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <RunBreadcrumb
        run={run}
        breadcrumbs={breadcrumbs}
        langfuseUrl={latest?.langfuse_url ?? null}
        hashContent={latest?.hash_content ?? run.run_id}
      />
      <div className="flex-1 overflow-hidden">
        <DashboardRenderer
          layout={layout}
          context={{ runId, algorithmPath: run.algorithm_path ?? "" }}
        />
      </div>
    </div>
  );
}

function RunBreadcrumb({
  run,
  breadcrumbs,
  langfuseUrl,
  hashContent,
}: {
  run: RunSummary;
  breadcrumbs: BreadcrumbItem[];
  langfuseUrl?: string | null;
  hashContent?: string | null;
}) {
  const className = run.algorithm_class ?? run.algorithm_path?.split(".").at(-1) ?? "Algorithm";
  const totalTokens = run.prompt_tokens + run.completion_tokens;
  const cost = run.cost?.cost_usd;

  return (
    <Breadcrumb
      items={[...breadcrumbs, { label: className }, { label: run.run_id, mono: true }]}
      trailing={
        <>
          <HashTag hash={hashContent ?? run.run_id} dotOnly size="sm" />
          {run.state === "running" ? (
            <Pill tone="live" pulse size="sm">
              live
            </Pill>
          ) : run.state === "error" ? (
            <Pill tone="error" size="sm">
              error
            </Pill>
          ) : (
            <Pill tone="ok" size="sm">
              ended
            </Pill>
          )}
          <Pill tone="algo" size="sm">
            algo
          </Pill>
          <Metric label="ago" value={formatRelativeTime(run.started_at)} />
          <Metric label="dur" value={formatDurationMs(run.duration_ms)} />
          <Metric
            label="tok"
            value={formatTokensOrUnavailable(totalTokens)}
            {...(hasTokenUsage(run.prompt_tokens, run.completion_tokens)
              ? { sub: formatTokenPairOrUnavailable(run.prompt_tokens, run.completion_tokens) }
              : {})}
          />
          <Metric label="$" value={formatCostOrUnavailable(cost)} />
          {langfuseUrl ? (
            <a
              href={langfuseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
              title="Open in Langfuse"
            >
              langfuse
              <ExternalLink size={11} />
            </a>
          ) : null}
        </>
      }
    />
  );
}
