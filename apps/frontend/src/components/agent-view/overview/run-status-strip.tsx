import { HashTag, Metric, Pill, StatusDot } from "@/components/ui";
import { RunInvocationsResponse, RunSummary } from "@/lib/types";
import {
  formatCostOrUnavailable,
  formatTokenPairOrUnavailable,
  formatTokensOrUnavailable,
} from "@/lib/usage";
import { formatDurationMs, truncateMiddle } from "@/lib/utils";
import * as Popover from "@radix-ui/react-popover";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

export interface RunStatusStripProps {
  dataSummary?: unknown;
  dataInvocations?: unknown;
  sourceSummary?: unknown;
  sourceInvocations?: unknown;
  runId?: string;
}

export function RunStatusStrip(props: RunStatusStripProps) {
  const summary = RunSummary.safeParse(props.dataSummary ?? props.sourceSummary);
  const invocations = RunInvocationsResponse.safeParse(
    props.dataInvocations ?? props.sourceInvocations,
  );
  const run = summary.success ? summary.data : null;
  const rows = invocations.success ? invocations.data.invocations : [];
  const latest = rows[rows.length - 1] ?? null;
  const hash = latest?.hash_content ?? run?.hash_content ?? run?.run_id ?? props.runId ?? null;
  const latency = latest?.latency_ms ?? run?.duration_ms ?? null;
  const prompt = latest?.prompt_tokens ?? run?.prompt_tokens ?? null;
  const completion = latest?.completion_tokens ?? run?.completion_tokens ?? null;
  const totalTokens = (prompt ?? 0) + (completion ?? 0);
  const cost = latest?.cost_usd ?? run?.cost?.cost_usd ?? null;
  const state = run?.state ?? (latest?.status === "error" ? "error" : "ended");
  const [copied, setCopied] = useState(false);

  const copyHash = () => {
    if (!hash) return;
    navigator.clipboard.writeText(hash).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 900);
    });
  };

  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2">
      <span className="inline-flex items-center gap-1.5">
        <StatusDot
          identity={hash}
          state={state === "running" ? "running" : state === "error" ? "error" : "ended"}
          size="sm"
        />
        <span className="text-[12px] font-medium text-text">
          {state === "error" ? "err" : "ok"}
        </span>
      </span>
      <button
        type="button"
        onClick={copyHash}
        className="inline-flex items-center gap-1.5 rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted transition-colors hover:border-border-strong hover:text-text"
      >
        <HashTag hash={hash} mono size="sm" />
        {copied ? <Check size={12} className="text-[--color-ok]" /> : <Copy size={12} />}
      </button>
      <StatePopover
        hash={hash}
        runId={props.runId ?? run?.run_id ?? null}
        state={state}
        invocations={rows}
      />
      <Metric label="latency" value={formatDurationMs(latency)} />
      <Metric
        label="tokens"
        value={formatTokensOrUnavailable(totalTokens)}
        sub={formatTokenPairOrUnavailable(prompt, completion)}
      />
      <Metric label="cost" value={formatCostOrUnavailable(cost)} />
    </div>
  );
}

function StatePopover({
  hash,
  runId,
  state,
  invocations,
}: {
  hash: string | null;
  runId: string | null;
  state: "running" | "ended" | "error";
  invocations: RunInvocationsResponse["invocations"];
}) {
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button type="button">
          <Pill
            tone={state === "running" ? "live" : state === "error" ? "error" : "ok"}
            pulse={state === "running"}
          >
            {state === "running" ? "running" : state}
          </Pill>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          sideOffset={6}
          className="z-50 w-72 rounded-md border border-border-strong bg-bg-1 p-2 shadow-[var(--shadow-popover)]"
        >
          <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
            sibling invocations
          </div>
          <div className="max-h-48 overflow-auto">
            {invocations.length === 0 ? (
              <div className="rounded bg-bg-inset p-2 text-[12px] text-muted-2">
                no invocation rows captured yet
              </div>
            ) : (
              invocations.map((row) => (
                <div
                  key={row.id}
                  className="flex items-center justify-between gap-2 rounded px-2 py-1.5 text-[12px] text-muted"
                >
                  <span className="min-w-0 truncate font-mono">{truncateMiddle(row.id, 18)}</span>
                  <span className="font-mono tabular-nums">{formatDurationMs(row.latency_ms)}</span>
                </div>
              ))
            )}
          </div>
          {hash && runId ? (
            <Link
              to={`/agents/${hash}/runs`}
              className="mt-2 inline-flex h-7 items-center rounded border border-border bg-bg-2 px-2 text-[12px] text-accent transition-colors hover:border-border-strong"
            >
              View all invocations
            </Link>
          ) : null}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
