import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { HashTag, Metric, PanelCard, PanelGrid, Pill, Sparkline, StatusDot } from "@/components/ui";
import { hashColor } from "@/lib/hash-color";
import { type RunInvocation, RunInvocationsResponse, RunSummary } from "@/lib/types";
import {
  formatCostOrUnavailable,
  formatTokenPairOrUnavailable,
  formatTokensOrUnavailable,
  hasTokenUsage,
} from "@/lib/usage";
import { formatDurationMs, formatRelativeTime } from "@/lib/utils";
import { ArrowRight, ExternalLink } from "lucide-react";
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
  if (rows.length === 1) {
    const row = rows[0];
    if (!row) return <Empty />;
    return <SingleInvocation row={row} runId={props.runId ?? null} />;
  }
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

function SingleInvocation({ row, runId }: { row: RunInvocation; runId: string | null }) {
  const ok = row.status === "ok";
  const ident = row.hash_content ?? runId ?? "row";
  return (
    <PanelCard
      flush
      eyebrow={
        <span className="flex items-center gap-1.5">
          <StatusDot identity={ident} state={ok ? "ended" : "error"} size="sm" />
          <span>Latest invocation</span>
        </span>
      }
      title={
        <span className="flex flex-wrap items-center gap-2">
          {ok ? <Pill tone="ok" size="sm">ok</Pill> : <Pill tone="error" size="sm">error</Pill>}
          {row.hash_content ? <HashTag hash={row.hash_content} mono size="sm" /> : null}
          <Metric label="ago" value={formatRelativeTime(row.started_at)} />
          <Metric label="latency" value={formatDurationMs(row.latency_ms ?? null)} />
          <Metric
            label="tokens"
            value={formatTokenPairOrUnavailable(row.prompt_tokens, row.completion_tokens)}
            {...(hasTokenUsage(row.prompt_tokens, row.completion_tokens)
              ? { sub: "in / out" }
              : {})}
          />
          <Metric label="cost" value={formatCostOrUnavailable(row.cost_usd)} />
        </span>
      }
      toolbar={
        row.langfuse_url ? (
          <a
            href={row.langfuse_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
          >
            Langfuse
            <ExternalLink size={11} />
          </a>
        ) : null
      }
    >
      {!ok && row.error ? (
        <div className="border-b border-border bg-[--color-err-dim]/30 px-3 py-2 font-mono text-[11px] text-[--color-err]">
          {row.error}
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-3 p-3 lg:grid-cols-2">
        <IOFieldPreview label="Input" data={row.input} defaultExpanded />
        <IOFieldPreview label="Output" data={row.output} defaultExpanded={!ok} />
      </div>
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
            <Pill tone="ok" size="sm">all ok</Pill>
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
