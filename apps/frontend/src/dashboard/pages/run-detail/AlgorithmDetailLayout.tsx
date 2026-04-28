import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import { EmptyState } from "@/components/ui";
import { useManifest, useRunEvents, useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { resolveLayout } from "@/layouts";
import type { RunSummary } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import { useEventBufferStore } from "@/stores";
import { useRunStore } from "@/stores/run";
import { ChevronRight } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

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

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Key on runId so swapping between two OPROOptimizer (or any
          two algo) instances fully remounts the renderer; otherwise
          the stale query cache from the previous run flashes the
          old tabs and data. */}
      <DashboardRenderer
        key={runId}
        layout={layout}
        context={{
          runId,
          algorithmPath: run.algorithm_path ?? "",
          langfuseUrl: derivedLangfuseUrl ?? "",
        }}
        tabsTrailing={<RunTabsBreadcrumb run={run} section={isOpro ? "OPRO" : "Algorithms"} />}
      />
    </div>
  );
}

function RunTabsBreadcrumb({ run, section }: { run: RunSummary; section: "Algorithms" | "OPRO" }) {
  const className = run.algorithm_class ?? run.algorithm_path?.split(".").at(-1) ?? "Algorithm";
  const shortRunId = truncateMiddle(run.run_id, 16);
  const paramPath = (() => {
    for (const it of run.iterations ?? []) {
      const meta = (it as { metadata?: { param_path?: unknown } }).metadata;
      const pp = meta?.param_path;
      if (typeof pp === "string" && pp) return pp;
    }
    return null;
  })();
  const sectionHref = section === "OPRO" ? "/opro" : "/algorithms";
  const items = [
    { label: section, to: sectionHref, mono: false },
    { label: className, mono: false },
    ...(paramPath ? [{ label: paramPath, mono: true }] : []),
    { label: shortRunId, mono: true },
  ];

  return (
    <nav
      aria-label="algorithm breadcrumb"
      className="flex min-w-0 items-center gap-1.5 text-[12px]"
    >
      {items.map((item, index) => {
        const last = index === items.length - 1;
        const labelClass = item.mono ? "font-mono text-[11px]" : "";
        return (
          <span key={`${item.label}-${index}`} className="flex min-w-0 items-center gap-1.5">
            {item.to ? (
              <Link
                to={item.to}
                className="min-w-0 truncate text-muted transition-colors hover:text-text"
              >
                <span className={labelClass}>{item.label}</span>
              </Link>
            ) : (
              <span
                className={`${labelClass} min-w-0 truncate ${last ? "text-text" : "text-muted"}`}
              >
                {item.label}
              </span>
            )}
            {!last ? (
              <ChevronRight aria-hidden size={12} className="flex-shrink-0 text-muted-2" />
            ) : null}
          </span>
        );
      })}
    </nav>
  );
}
