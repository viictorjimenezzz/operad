import { Metric, Pill, StatusDot } from "@/components/ui";
import { RunInvocationsResponse, RunSummary } from "@/lib/types";
import { formatCostOrUnavailable, formatTokensOrUnavailable } from "@/lib/usage";
import { formatDurationMs, formatRelativeTime } from "@/lib/utils";
import { ExternalLink } from "lucide-react";

export interface ActivityStripProps {
  dataSummary?: unknown;
  dataInvocations?: unknown;
  sourceSummary?: unknown;
  sourceInvocations?: unknown;
  runId?: string;
}

export function ActivityStrip(props: ActivityStripProps) {
  const summary = RunSummary.safeParse(props.dataSummary ?? props.sourceSummary);
  const invocations = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.sourceInvocations,
  );
  const run = summary.success ? summary.data : null;
  const rows = invocations.success ? invocations.data.invocations : [];
  const latest = rows[rows.length - 1] ?? null;
  const latency = latest?.latency_ms ?? run?.duration_ms ?? null;
  const prompt = latest?.prompt_tokens ?? run?.prompt_tokens ?? null;
  const completion = latest?.completion_tokens ?? run?.completion_tokens ?? null;
  const totalTokens = (prompt ?? 0) + (completion ?? 0);
  const cost = latest?.cost_usd ?? run?.cost?.cost_usd ?? null;
  const state = run?.state ?? (latest?.status === "error" ? "error" : "ended");
  const hash = latest?.hash_content ?? run?.hash_content ?? null;
  const langfuseUrl = latest?.langfuse_url ?? null;
  const startedAt = run?.started_at ?? null;

  return (
    <div className="flex min-h-8 flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-border px-0 py-2">
      <span className="inline-flex items-center gap-1.5">
        <StatusDot
          identity={hash}
          state={state === "running" ? "running" : state === "error" ? "error" : "ended"}
          size="sm"
        />
        <Pill
          tone={state === "running" ? "live" : state === "error" ? "error" : "ok"}
          pulse={state === "running"}
        >
          {state === "running" ? "running" : state === "error" ? "error" : "ended"}
        </Pill>
      </span>
      {startedAt != null ? (
        <span className="text-[12px] text-muted">{formatRelativeTime(startedAt)}</span>
      ) : null}
      <Metric label="duration" value={formatDurationMs(latency)} />
      <Metric label="tokens" value={formatTokensOrUnavailable(totalTokens)} />
      <Metric label="cost" value={formatCostOrUnavailable(cost)} />
      {langfuseUrl ? (
        <a
          href={langfuseUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[12px] text-accent hover:text-accent-strong"
        >
          langfuse
          <ExternalLink size={11} />
        </a>
      ) : null}
    </div>
  );
}
