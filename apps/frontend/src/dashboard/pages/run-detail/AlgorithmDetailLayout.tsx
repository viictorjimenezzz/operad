import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import {
  Breadcrumb,
  type BreadcrumbItem,
  EmptyState,
  HashTag,
  Metric,
  Pill,
} from "@/components/ui";
import { useManifest, useRunEvents, useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { resolveLayout } from "@/layouts";
import { computeAlgorithmKpis } from "@/lib/algorithm-kpis";
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
  const manifest = useManifest();
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

  // Optimisers and pure-orchestrator algorithms (OPRO, EvoGradient,
  // Sweep, ...) often have no agent_event under the algorithm's *own*
  // root_agent_path, so `latest.langfuse_url` is null. Fall back to
  // deriving the deep-link from the manifest base URL + run_id so the
  // breadcrumb still gets a langfuse jump-out.
  const derivedLangfuseUrl = useMemo(() => {
    if (latest?.langfuse_url) return latest.langfuse_url;
    if (!runId) return null;
    const base = manifest.data?.langfuseUrl;
    return base ? `${base.replace(/\/$/, "")}/trace/${runId}` : null;
  }, [latest, runId, manifest.data?.langfuseUrl]);

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
        langfuseUrl={derivedLangfuseUrl}
        hashContent={latest?.hash_content ?? run.run_id}
      />
      <div className="flex-1 overflow-hidden">
        {/* Key on runId so swapping between two OPROOptimizer (or any
            two algo) instances fully remounts the renderer; otherwise
            the stale query cache from the previous run flashes the
            old tabs and data. */}
        <DashboardRenderer
          key={runId}
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
  // Show a truncated id in the breadcrumb so two distinct OPROOptimizer
  // (or any two algo) instances are visually distinguishable without
  // overflowing the row with a full hash.
  const shortRunId = run.run_id.length > 12 ? `${run.run_id.slice(0, 8)}…${run.run_id.slice(-4)}` : run.run_id;
  // For optimisers (OPRO/EvoGradient) include the parameter path being
  // optimised. Without this the breadcrumb of two optimiser sessions that
  // target different params reads identically.
  const paramPath = (() => {
    for (const it of run.iterations ?? []) {
      const meta = (it as { metadata?: { param_path?: unknown } }).metadata;
      const pp = meta?.param_path;
      if (typeof pp === "string" && pp) return pp;
    }
    return null;
  })();

  return (
    <Breadcrumb
      items={[
        ...breadcrumbs,
        { label: className },
        ...(paramPath ? [{ label: paramPath, mono: true }] : []),
        { label: shortRunId, mono: true },
      ]}
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
            {hasTokenUsage(run.prompt_tokens, run.completion_tokens) ? (
              <Metric
                label="tok"
                value={formatTokensOrUnavailable(totalTokens)}
                sub={formatTokenPairOrUnavailable(run.prompt_tokens, run.completion_tokens)}
              />
            ) : null}
            {typeof cost === "number" && Number.isFinite(cost) && cost > 0 ? (
              <Metric label="$" value={formatCostOrUnavailable(cost)} />
            ) : null}
            {computeAlgorithmKpis(run).map((kpi) => (
              <Metric key={kpi.label} label={kpi.label} value={kpi.value} sub={kpi.sub} />
            ))}
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
