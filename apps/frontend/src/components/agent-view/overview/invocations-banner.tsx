import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { HashTag, Metric, Pill, Sparkline } from "@/components/ui";
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

  if (rows.length === 0) {
    return <Empty />;
  }

  if (rows.length === 1) {
    const row = rows[0];
    if (!row) return <Empty />;
    return <SingleInvocation row={row} />;
  }

  return <MultiSummary rows={rows} runId={props.runId ?? null} />;
}

// ---------- 0 invocations ----------

function Empty() {
  return (
    <div className="rounded-lg border border-border bg-bg-1 px-4 py-5">
      <Pill tone="live" pulse>
        waiting for first invocation
      </Pill>
      <div className="mt-2 text-[13px] text-muted">
        The agent is built but no invocation has produced output yet.
      </div>
    </div>
  );
}

// ---------- 1 invocation ----------

function SingleInvocation({ row }: { row: RunInvocation }) {
  const ok = row.status === "ok";

  return (
    <article className="overflow-hidden rounded-lg border border-border bg-bg-1">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-bg-2/40 px-4 py-2">
        {ok ? <Pill tone="ok">ok</Pill> : <Pill tone="error">error</Pill>}
        {row.hash_content ? <HashTag hash={row.hash_content} mono size="sm" /> : null}
        <div className="flex items-center gap-4">
          <Metric label="ago" value={formatRelativeTime(row.started_at)} />
          <Metric label="latency" value={formatDurationMs(row.latency_ms ?? null)} />
          <Metric
            label="tokens"
            value={formatTokenPairOrUnavailable(row.prompt_tokens, row.completion_tokens)}
            sub={hasTokenUsage(row.prompt_tokens, row.completion_tokens) ? "in / out" : undefined}
          />
          <Metric label="cost" value={formatCostOrUnavailable(row.cost_usd)} />
        </div>
        {row.langfuse_url ? (
          <a
            href={row.langfuse_url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
          >
            Open in Langfuse
            <ExternalLink size={11} />
          </a>
        ) : null}
      </header>

      {!ok && row.error ? (
        <div className="border-b border-border bg-[--color-err-dim]/30 px-4 py-2 font-mono text-[11px] text-[--color-err]">
          {row.error}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 p-4 lg:grid-cols-2">
        <IOFieldPreview label="Input" data={row.input} defaultExpanded />
        <IOFieldPreview label="Output" data={row.output} defaultExpanded={!ok} />
      </div>
    </article>
  );
}

// ---------- N invocations ----------

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
    <article className="overflow-hidden rounded-lg border border-border bg-bg-1">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-bg-2/40 px-4 py-2">
        <span className="text-[13px] font-medium text-text">{stats.count} invocations</span>
        {stats.errors > 0 ? (
          <Pill tone="error">
            {stats.errors} error{stats.errors === 1 ? "" : "s"}
          </Pill>
        ) : (
          <Pill tone="ok">all ok</Pill>
        )}
        <div className="ml-auto flex items-center gap-4">
          <Metric label="avg latency" value={formatDurationMs(stats.avgLatency)} />
          <Metric label="total tokens" value={formatTokensOrUnavailable(stats.tokens)} />
          <Metric
            label="total cost"
            value={stats.costCount > 0 ? formatCostOrUnavailable(stats.cost) : "unavailable"}
          />
        </div>
      </header>
      <div className="flex items-center gap-3 px-4 py-2">
        <div className="text-[10px] uppercase tracking-[0.06em] text-muted-2">latency</div>
        <Sparkline values={latencyValues} width={320} height={28} className="text-accent" />
        {runId ? (
          <Link
            to={`/runs/${runId}/invocations`}
            className="ml-auto inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
          >
            View all {stats.count} invocations
            <ArrowRight size={12} />
          </Link>
        ) : null}
      </div>
    </article>
  );
}

// ---------- skeleton ----------

function Skeleton() {
  return (
    <div className="rounded-lg border border-border bg-bg-1 p-4">
      <div className="h-4 w-40 animate-pulse rounded bg-bg-3" />
      <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-7 animate-pulse rounded bg-bg-2" />
        ))}
      </div>
    </div>
  );
}
