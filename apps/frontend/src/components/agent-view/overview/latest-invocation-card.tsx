import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { Eyebrow, HashTag, Pill, StatTile } from "@/components/ui";
import {
  type RunInvocation,
  RunInvocationsResponse,
  RunSummary,
  type RunSummary as RunSummaryType,
} from "@/lib/types";
import { formatCostOrUnavailable, formatTokenPairOrUnavailable, hasTokenUsage } from "@/lib/usage";
import { cn, formatDurationMs, formatRelativeTime } from "@/lib/utils";
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
  const rawSummary = props.dataSummary ?? props.summary;
  const rawInvocations = props.dataInvocations ?? props.invocations;

  const summaryParsed = RunSummary.safeParse(rawSummary);
  const invocationsParsed = RunInvocationsResponse.safeParse(rawInvocations);

  if (!summaryParsed.success || !invocationsParsed.success) {
    return <Skeleton />;
  }

  const summary = summaryParsed.data;
  const rows = invocationsParsed.data.invocations;
  const latest = rows[rows.length - 1];

  if (!latest) {
    return (
      <div className="rounded-xl border border-border bg-bg-1 p-6 text-[13px] text-muted">
        <Pill tone="live" pulse>
          waiting for first invocation
        </Pill>
        <div className="mt-2">The agent is built but no invocation has produced output yet.</div>
      </div>
    );
  }

  return <LatestInvocationCardImpl summary={summary} latest={latest} />;
}

function LatestInvocationCardImpl({
  summary,
  latest,
}: { summary: RunSummaryType; latest: RunInvocation }) {
  const inputDescriptions = useMemo(() => extractFieldDescriptions(summary, "input"), [summary]);
  const outputDescriptions = useMemo(() => extractFieldDescriptions(summary, "output"), [summary]);

  const ok = latest.status === "ok";

  return (
    <article className="overflow-hidden rounded-2xl border border-border bg-bg-1 shadow-[var(--shadow-card-soft)]">
      <header className="flex items-start gap-4 border-b border-border bg-bg-2/40 px-5 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Eyebrow>Latest invocation</Eyebrow>
            {ok ? (
              <Pill tone="ok" size="sm">
                ok
              </Pill>
            ) : (
              <Pill tone="error" size="sm">
                error
              </Pill>
            )}
            {latest.hash_content ? <HashTag hash={latest.hash_content} size="sm" mono /> : null}
            {latest.langfuse_url ? (
              <a
                href={latest.langfuse_url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
              >
                Open in Langfuse
                <ExternalLink size={11} />
              </a>
            ) : null}
          </div>
          {!ok && latest.error ? (
            <div className="mt-2 rounded-lg border border-[--color-err-dim] bg-[--color-err-dim]/30 px-3 py-2 font-mono text-[11px] text-[--color-err]">
              {latest.error}
            </div>
          ) : null}
        </div>
      </header>

      <div className="grid grid-cols-2 gap-4 px-5 pt-5 sm:grid-cols-4">
        <StatTile label="started" value={formatRelativeTime(latest.started_at)} size="sm" />
        <StatTile label="latency" value={formatDurationMs(latest.latency_ms ?? null)} size="sm" />
        <StatTile
          label="tokens"
          value={formatTokenPairOrUnavailable(latest.prompt_tokens, latest.completion_tokens)}
          sub={
            hasTokenUsage(latest.prompt_tokens, latest.completion_tokens) ? "in / out" : undefined
          }
          size="sm"
        />
        <StatTile label="cost" value={formatCostOrUnavailable(latest.cost_usd)} size="sm" />
      </div>

      <div className="grid grid-cols-1 gap-4 px-5 py-5 lg:grid-cols-2">
        <IOFieldPreview
          label="Input"
          data={latest.input}
          descriptions={inputDescriptions}
          defaultExpanded={false}
        />
        <IOFieldPreview
          label="Output"
          data={latest.output}
          descriptions={outputDescriptions}
          defaultExpanded={!ok}
        />
      </div>
    </article>
  );
}

function Skeleton() {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-bg-1 p-5 shadow-[var(--shadow-card-soft)]",
      )}
    >
      <div className="h-4 w-40 animate-pulse rounded bg-bg-3" />
      <div className="mt-4 grid grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-bg-2" />
        ))}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="h-32 animate-pulse rounded bg-bg-2" />
        <div className="h-32 animate-pulse rounded bg-bg-2" />
      </div>
    </div>
  );
}

function extractFieldDescriptions(
  summary: RunSummaryType,
  side: "input" | "output",
): Record<string, string> | undefined {
  // Optional: dashboard summary may include schema documentation in the future.
  // For now we return undefined so the FieldTree falls back to no descriptions.
  void summary;
  void side;
  return undefined;
}
