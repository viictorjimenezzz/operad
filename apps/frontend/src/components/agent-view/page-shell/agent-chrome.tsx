import {
  AgentTabs,
  type AgentTabSpec,
} from "@/components/agent-view/page-shell/agent-tabs";
import { Breadcrumb, HashTag, Metric, Pill, type BreadcrumbItem } from "@/components/ui";
import type { RunSummary } from "@/lib/types";
import {
  formatCostOrUnavailable,
  formatTokenPairOrUnavailable,
  formatTokensOrUnavailable,
  hasTokenUsage,
} from "@/lib/usage";
import { formatDurationMs, formatRelativeTime } from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

/**
 * Slim W&B-style chrome: a breadcrumb row + a tab strip. The hero is
 * gone; KPIs live inside the canvas now.
 */
export interface AgentChromeProps {
  run: RunSummary;
  langfuseUrl?: string | null;
  hashContent?: string | null;
  basePath: string;
  tabs: AgentTabSpec[];
  rightActions?: ReactNode;
  /** Optional preceding breadcrumb crumbs (e.g. group > run). */
  breadcrumbs?: BreadcrumbItem[];
}

export function AgentChrome({
  run,
  langfuseUrl,
  hashContent,
  basePath,
  tabs,
  rightActions,
  breadcrumbs,
}: AgentChromeProps) {
  const className = run.algorithm_class ?? run.root_agent_path?.split(".").at(-1) ?? "Agent";
  const totalTokens = run.prompt_tokens + run.completion_tokens;
  const cost = run.cost?.cost_usd;
  const idHash = hashContent ?? run.run_id;

  const items: BreadcrumbItem[] = [
    ...(breadcrumbs ?? [{ label: "Runs", to: "/agents" }]),
    { label: className },
    { label: run.run_id, mono: true },
  ];

  return (
    <header className="flex-shrink-0">
      <Breadcrumb
        items={items}
        trailing={
          <>
            <HashTag hash={idHash} dotOnly size="sm" />
            {run.state === "running" ? (
              <Pill tone="live" pulse size="sm">
                live
              </Pill>
            ) : run.state === "error" ? (
              <Pill tone="error" size="sm">
                error
              </Pill>
            ) : (
              <Pill tone="ok" size="sm">
                ended
              </Pill>
            )}
            {run.is_algorithm ? <Pill tone="algo" size="sm">algo</Pill> : null}
            <Metric label="ago" value={formatRelativeTime(run.started_at)} />
            <Metric label="dur" value={formatDurationMs(run.duration_ms)} />
            {hasTokenUsage(run.prompt_tokens, run.completion_tokens) ? (
              <Metric
                label="tok"
                value={formatTokensOrUnavailable(totalTokens)}
                sub={formatTokenPairOrUnavailable(run.prompt_tokens, run.completion_tokens)}
              />
            ) : null}
            {typeof cost === "number" && Number.isFinite(cost) && cost > 0 ? (
              <Metric label="$" value={formatCostOrUnavailable(cost)} />
            ) : null}
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
            {rightActions}
          </>
        }
      />
      <AgentTabs base={basePath} tabs={tabs} />
    </header>
  );
}
