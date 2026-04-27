import { Metric, PanelCard, PanelGrid, Pill, Sparkline, StatusDot } from "@/components/ui";
import { hashColor } from "@/lib/hash-color";
import { type RunInvocation, RunInvocationsResponse, RunSummary } from "@/lib/types";
import { formatCostOrUnavailable, formatTokensOrUnavailable } from "@/lib/usage";
import { formatDurationMs } from "@/lib/utils";
import { ArrowRight } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";

export interface InvocationsBannerProps {
  dataSummary?: unknown;
  dataInvocations?: unknown;
  summary?: unknown;
  invocations?: unknown;
  runId?: string;
}

export function InvocationsBanner(props: InvocationsBannerProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  const invocationsParsed = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.invocations,
  );

  if (!summaryParsed.success || !invocationsParsed.success) {
    return <Skeleton />;
  }

  const rows = invocationsParsed.data.invocations;

  if (rows.length === 0) return <Empty />;
  if (rows.length === 1) return null;
  return <MultiSummary rows={rows} runId={props.runId ?? null} />;
}

function Empty() {
  return (
    <PanelCard
      eyebrow={
        <span className="flex items-center gap-1.5">
          <StatusDot state="running" size="sm" pulse />
          <span>Live</span>
        </span>
      }
      title="waiting for first invocation"
    >
      <span className="text-[12px] text-muted">
        The agent is built but no invocation has produced output yet.
      </span>
    </PanelCard>
  );
}

function MultiSummary({ rows, runId }: { rows: RunInvocation[]; runId: string | null }) {
  const stats = useMemo(() => {
    const latencies = rows
      .map((r) => r.latency_ms)
      .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    const totals = rows.reduce(
      (acc, r) => {
        acc.tokens += (r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0);
        if (typeof r.cost_usd === "number") {
          acc.cost += r.cost_usd;
          acc.costCount += 1;
        }
        return acc;
      },
      { tokens: 0, cost: 0, costCount: 0 },
    );
    const avgLatency =
      latencies.length > 0 ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null;
    const errors = rows.filter((r) => r.status === "error").length;
    return {
      count: rows.length,
      avgLatency,
      tokens: totals.tokens,
      cost: totals.cost,
      costCount: totals.costCount,
      errors,
    };
  }, [rows]);
  const latencyValues = useMemo(() => rows.map((r) => r.latency_ms ?? null), [rows]);
  return (
    <PanelCard
      eyebrow="This run"
      title={
        <span className="flex items-center gap-3">
          <span>{stats.count} invocations</span>
          {stats.errors > 0 ? (
            <Pill tone="error" size="sm">
              {stats.errors} error{stats.errors === 1 ? "" : "s"}
            </Pill>
          ) : (
            <Pill tone="ok" size="sm">
              all ok
            </Pill>
          )}
        </span>
      }
      toolbar={
        runId ? (
          <Link
            to={`/runs/${runId}/invocations`}
            className="inline-flex items-center gap-1 text-[12px] text-accent hover:text-[--color-accent-strong]"
          >
            View all
            <ArrowRight size={12} />
          </Link>
        ) : null
      }
    >
      <PanelGrid cols={4} gap="sm">
        <Metric label="avg latency" value={formatDurationMs(stats.avgLatency)} />
        <Metric label="total tokens" value={formatTokensOrUnavailable(stats.tokens)} />
        <Metric
          label="total cost"
          value={stats.costCount > 0 ? formatCostOrUnavailable(stats.cost) : "unavailable"}
        />
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.06em] text-muted-2">latency</span>
          <Sparkline
            values={latencyValues}
            width={140}
            height={22}
            color={hashColor(runId ?? "row")}
          />
        </div>
      </PanelGrid>
    </PanelCard>
  );
}

function Skeleton() {
  return (
    <PanelCard eyebrow="Run" title="loading…">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-7 animate-pulse rounded bg-bg-2" />
        ))}
      </div>
    </PanelCard>
  );
}
