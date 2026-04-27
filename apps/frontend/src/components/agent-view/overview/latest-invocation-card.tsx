import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { HashTag, Metric, PanelCard, Pill, StatusDot } from "@/components/ui";
import {
  type RunInvocation,
  RunInvocationsResponse,
  RunSummary,
  type RunSummary as RunSummaryType,
} from "@/lib/types";
import { formatCostOrUnavailable, formatTokenPairOrUnavailable, hasTokenUsage } from "@/lib/usage";
import { formatDurationMs, formatRelativeTime } from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import { useMemo } from "react";

export interface LatestInvocationCardProps {
  summary?: unknown;
  invocations?: unknown;
  dataSummary?: unknown;
  dataInvocations?: unknown;
  runId?: string;
}

export function LatestInvocationCard(props: LatestInvocationCardProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  const invocationsParsed = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.invocations,
  );
  if (!summaryParsed.success || !invocationsParsed.success) {
    return <Skeleton />;
  }
  const latest = invocationsParsed.data.invocations[invocationsParsed.data.invocations.length - 1];
  if (!latest) {
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
  return <Impl summary={summaryParsed.data} latest={latest} />;
}

function Impl({ summary, latest }: { summary: RunSummaryType; latest: RunInvocation }) {
  const inputDescriptions = useMemo(() => extract(summary, "input"), [summary]);
  const outputDescriptions = useMemo(() => extract(summary, "output"), [summary]);
  const ok = latest.status === "ok";
  const ident = latest.hash_content ?? latest.id;
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
          {latest.hash_content ? <HashTag hash={latest.hash_content} mono size="sm" /> : null}
          <Metric label="ago" value={formatRelativeTime(latest.started_at)} />
          <Metric label="latency" value={formatDurationMs(latest.latency_ms ?? null)} />
          <Metric
            label="tokens"
            value={formatTokenPairOrUnavailable(latest.prompt_tokens, latest.completion_tokens)}
            {...(hasTokenUsage(latest.prompt_tokens, latest.completion_tokens)
              ? { sub: "in / out" }
              : {})}
          />
          <Metric label="cost" value={formatCostOrUnavailable(latest.cost_usd)} />
        </span>
      }
      toolbar={
        latest.langfuse_url ? (
          <a
            href={latest.langfuse_url}
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
      {!ok && latest.error ? (
        <div className="border-b border-border bg-[--color-err-dim]/30 px-3 py-2 font-mono text-[11px] text-[--color-err]">
          {latest.error}
        </div>
      ) : null}
      <div className="grid grid-cols-1 gap-3 p-3 lg:grid-cols-2">
        <IOFieldPreview
          label="Input"
          data={latest.input}
          descriptions={inputDescriptions}
          defaultExpanded
        />
        <IOFieldPreview
          label="Output"
          data={latest.output}
          descriptions={outputDescriptions}
          defaultExpanded={!ok}
        />
      </div>
    </PanelCard>
  );
}

function Skeleton() {
  return (
    <PanelCard eyebrow="Latest invocation" title="loading…">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-7 animate-pulse rounded bg-bg-2" />
        ))}
      </div>
    </PanelCard>
  );
}

function extract(_summary: RunSummaryType, _side: "input" | "output"): Record<string, string> | undefined {
  return undefined;
}
