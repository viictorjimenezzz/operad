import { HashTag, Pill } from "@/components/ui";
import { hashColor, hashColorDim } from "@/lib/hash-color";
import type { RunSummary } from "@/lib/types";
import {
  cn,
  formatCost,
  formatDurationMs,
  formatRelativeTime,
  formatTokens,
  truncateMiddle,
} from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import { useMemo } from "react";

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
  const tint = useMemo(
    () => ({
      bg: hashColorDim(identityHash),
      ring: hashColor(identityHash),
    }),
    [identityHash],
  );

  return (
    <div
      className="relative overflow-hidden border-b border-border bg-bg-1 px-6 py-5"
      style={{
        backgroundImage: `linear-gradient(135deg, ${tint.bg} 0%, transparent 60%)`,
      }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -left-1 top-1/2 h-32 w-1 -translate-y-1/2 rounded-r-full opacity-80"
        style={{ background: tint.ring }}
      />
      <div className="flex items-start gap-5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <HashTag hash={identityHash} dotOnly size="lg" />
            <h1 className="m-0 truncate text-[28px] font-medium leading-9 tracking-tight text-text">
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
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[12px] text-muted">
            <span title={run.run_id}>run {truncateMiddle(run.run_id, 22)}</span>
            {run.script ? (
              <>
                <span aria-hidden className="text-muted-2">
                  ·
                </span>
                <span className="truncate">{run.script}</span>
              </>
            ) : null}
            {langfuseUrl ? (
              <>
                <span aria-hidden className="text-muted-2">
                  ·
                </span>
                <a
                  href={langfuseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-accent hover:text-[--color-accent-strong]"
                >
                  langfuse <ExternalLink size={11} />
                </a>
              </>
            ) : null}
          </div>
        </div>
        <HeroStats run={run} />
      </div>
    </div>
  );
}

function HeroStats({ run }: { run: RunSummary }) {
  const totalTokens = run.prompt_tokens + run.completion_tokens;
  const cost = run.cost?.cost_usd;

  return (
    <div className="flex shrink-0 items-stretch gap-8 text-right">
      <Stat label="started" value={formatRelativeTime(run.started_at)} />
      <Stat label="duration" value={formatDurationMs(run.duration_ms)} />
      <Stat
        label="tokens"
        value={formatTokens(totalTokens)}
        sub={`${formatTokens(run.prompt_tokens)} in / ${formatTokens(run.completion_tokens)} out`}
      />
      <Stat label="cost" value={formatCost(cost)} />
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className={cn("flex flex-col items-end gap-0.5")}>
      <span className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
        {label}
      </span>
      <span className="text-[20px] font-medium leading-tight tabular-nums text-text">{value}</span>
      {sub ? <span className="font-mono text-[10px] text-muted-2">{sub}</span> : null}
    </div>
  );
}
