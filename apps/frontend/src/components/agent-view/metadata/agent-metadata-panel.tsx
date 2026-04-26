import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { InvocationsTable } from "@/components/agent-view/metadata/invocations-table";
import { ScriptOriginChip } from "@/components/agent-view/metadata/script-origin-chip";
import { Badge } from "@/components/ui/badge";
import { RunSummary } from "@/lib/types";
import {
  formatCost,
  formatDurationMs,
  formatRelativeTime,
  formatTokens,
  truncateMiddle,
} from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import { z } from "zod";

const InvocationRowSchema = z.object({
  hash_content: z.string().nullable().optional(),
  langfuse_url: z.string().nullable().optional(),
});
const InvocationsPayload = z.object({
  invocations: z.array(InvocationRowSchema).default([]),
});

interface AgentMetadataPanelProps {
  summary: unknown;
  invocations: unknown;
}

export function AgentMetadataPanel({ summary, invocations }: AgentMetadataPanelProps) {
  const summaryParsed = RunSummary.safeParse(summary);
  const invParsed = InvocationsPayload.safeParse(invocations);

  if (!summaryParsed.success) {
    return (
      <div className="rounded-md border border-border bg-bg-1 p-3 text-xs text-muted">
        loading agent metadata…
      </div>
    );
  }

  const run = summaryParsed.data;
  const latest = invParsed.success
    ? invParsed.data.invocations[invParsed.data.invocations.length - 1]
    : null;
  const className = run.algorithm_class ?? run.root_agent_path?.split(".").at(-1) ?? "Agent";
  const stateVariant = run.state === "running" ? "live" : run.state === "error" ? "error" : "ended";

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-md border border-border bg-bg-1 p-3">
        <div className="flex flex-wrap items-start gap-2">
          <div className="min-w-0 flex-1">
            <div className="font-mono text-lg text-text">{className}</div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <Badge variant="default">{run.is_algorithm ? "algorithm" : "agent"}</Badge>
              <Badge
                variant={stateVariant}
                className={run.state === "running" ? "animate-pulse" : ""}
              >
                {run.state}
              </Badge>
              <span
                className="rounded-full border border-border bg-bg-2 px-2 py-0.5 font-mono text-[11px] text-muted"
                title={run.run_id}
              >
                run {truncateMiddle(run.run_id, 18)}
              </span>
              <HashChip hash={latest?.hash_content} />
              <ScriptOriginChip script={run.script} />
              {latest?.langfuse_url ? (
                <a
                  href={latest.langfuse_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded border border-border bg-bg-2 px-2 py-0.5 text-[11px] text-muted hover:text-text"
                >
                  Langfuse
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : null}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted">
            <span>started</span>
            <span
              className="font-mono text-text"
              title={new Date(run.started_at * 1000).toLocaleString()}
            >
              {formatRelativeTime(run.started_at)}
            </span>
            <span>duration</span>
            <span className="font-mono text-text">{formatDurationMs(run.duration_ms)}</span>
            <span>tokens</span>
            <span className="font-mono text-text">
              {formatTokens(run.prompt_tokens)} / {formatTokens(run.completion_tokens)}
            </span>
            <span>cost</span>
            <span className="font-mono text-text">{formatCost(run.cost?.cost_usd)}</span>
          </div>
        </div>
      </div>
      <InvocationsTable summary={run} invocations={invocations} />
    </div>
  );
}
