import { HashTag, Metric, Pill } from "@/components/ui";
import type { RunSummary } from "@/lib/types";
import {
  formatCost,
  formatDurationMs,
  formatRelativeTime,
  formatTokens,
  truncateMiddle,
} from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

export interface AgentHeroProps {
  run: RunSummary;
  langfuseUrl?: string | null;
  hashContent?: string | null;
}

function classNameFor(run: RunSummary): string {
  if (run.algorithm_class) return run.algorithm_class;
  if (run.root_agent_path) {
    const tail = run.root_agent_path.split(".").at(-1);
    if (tail) return tail;
  }
  return "Agent";
}

export function AgentHero({ run, langfuseUrl, hashContent }: AgentHeroProps) {
  const className = classNameFor(run);
  const identityHash = hashContent ?? run.run_id;
  const totalTokens = run.prompt_tokens + run.completion_tokens;
  const cost = run.cost?.cost_usd;

  return (
    <div className="flex h-9 items-center gap-3 border-b border-border bg-bg px-3 text-[12px]">
      <Link to="/" className="text-muted-2 transition-colors hover:text-text">
        runs
      </Link>
      <span aria-hidden className="text-muted-2">
        /
      </span>
      <span title={run.run_id} className="font-mono text-[11px] text-muted">
        {truncateMiddle(run.run_id, 14)}
      </span>
      <span aria-hidden className="text-muted-2">
        ·
      </span>
      <HashTag hash={identityHash} dotOnly size="sm" />
      <h1 className="m-0 truncate text-[13px] font-medium tracking-tight text-text">
        {className}
      </h1>
      {run.state === "running" ? (
        <Pill tone="live" pulse>
          live
        </Pill>
      ) : run.state === "error" ? (
        <Pill tone="error">error</Pill>
      ) : (
        <Pill tone="ok">ended</Pill>
      )}
      {run.is_algorithm ? <Pill tone="algo">algorithm</Pill> : null}
      {run.script ? (
        <span
          className="hidden truncate font-mono text-[11px] text-muted-2 md:inline"
          title={run.script}
        >
          {run.script}
        </span>
      ) : null}
      <div className="ml-auto flex shrink-0 items-center gap-4">
        <Metric label="ago" value={formatRelativeTime(run.started_at)} />
        <Metric label="dur" value={formatDurationMs(run.duration_ms)} />
        <Metric
          label="tok"
          value={formatTokens(totalTokens)}
          sub={
            totalTokens > 0
              ? `${formatTokens(run.prompt_tokens)} in / ${formatTokens(run.completion_tokens)} out`
              : undefined
          }
        />
        <Metric label="$" value={formatCost(cost)} />
        {langfuseUrl ? (
          <a
            href={langfuseUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-[--color-accent-strong]"
            title="Open in Langfuse"
          >
            langfuse
            <ExternalLink size={11} />
          </a>
        ) : null}
      </div>
    </div>
  );
}
