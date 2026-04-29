import { DashboardRenderer } from "@/components/runtime/dashboard-renderer";
import { Breadcrumb, EmptyState, HashTag, Metric, Pill } from "@/components/ui";
import { useRunEvents, useRunSummary } from "@/hooks/use-runs";
import { resolveLayout } from "@/layouts";
import {
  formatCostOrUnavailable,
  formatTokenPairOrUnavailable,
  formatTokensOrUnavailable,
  hasTokenUsage,
} from "@/lib/usage";
import { formatDurationMs, formatRelativeTime } from "@/lib/utils";
import { useEventBufferStore } from "@/stores";
import { useRunStore } from "@/stores/run";
import { useEffect } from "react";
import { useParams } from "react-router-dom";

export function TrainingDetailLayout() {
  const { runId } = useParams<{ runId: string }>();
  const setCurrentRun = useRunStore((s) => s.setCurrentRun);
  const summary = useRunSummary(runId);
  const events = useRunEvents(runId);
  const ingest = useEventBufferStore((s) => s.ingest);

  useEffect(() => {
    setCurrentRun(runId ?? null);
    return () => setCurrentRun(null);
  }, [runId, setCurrentRun]);

  useEffect(() => {
    if (!events.data) return;
    for (const env of events.data.events) ingest(env);
  }, [events.data, ingest]);

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
  const totalTokens = run.prompt_tokens + run.completion_tokens;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb
        items={[
          { label: "Training", to: "/training" },
          { label: run.algorithm_class ?? "Trainer" },
          { label: run.run_id, mono: true },
        ]}
        trailing={
          <>
            <HashTag hash={run.run_id} dotOnly size="sm" />
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
            <Metric label="ago" value={formatRelativeTime(run.started_at)} />
            <Metric label="dur" value={formatDurationMs(run.duration_ms)} />
            <Metric
              label="tok"
              value={formatTokensOrUnavailable(totalTokens)}
              {...(hasTokenUsage(run.prompt_tokens, run.completion_tokens)
                ? { sub: formatTokenPairOrUnavailable(run.prompt_tokens, run.completion_tokens) }
                : {})}
            />
            <Metric label="$" value={formatCostOrUnavailable(run.cost?.cost_usd)} />
          </>
        }
      />
      <div className="flex-1 overflow-hidden">
        <DashboardRenderer
          key={`${runId}:${layout.algorithm}`}
          layout={layout}
          context={{ runId }}
        />
      </div>
    </div>
  );
}
