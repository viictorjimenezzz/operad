import { agentGroupTabs } from "@/components/agent-view/page-shell/agent-group-tabs";
import { EmptyState, HashTag, Pill } from "@/components/ui";
import { useAgentGroup, useAgentMeta } from "@/hooks/use-runs";
import { cn, truncateMiddle } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";

export function AgentGroupPage() {
  const { hashContent } = useParams<{ hashContent: string }>();
  if (!hashContent) return <EmptyState title="missing hash" />;
  return <AgentGroupPageInner hashContent={hashContent} />;
}

function AgentGroupPageInner({ hashContent }: { hashContent: string }) {
  const group = useAgentGroup(hashContent);
  const latestRun = group.data?.runs.at(-1) ?? null;
  const meta = useAgentMeta(latestRun?.run_id ?? null, latestRun?.root_agent_path ?? null);

  if (group.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted">
        loading group...
      </div>
    );
  }
  if (group.error || !group.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="group not found"
          description="this hash_content is no longer in the registry"
        />
      </div>
    );
  }

  const detail = group.data;
  // Prefer the user-declared class name (e.g. `research_analyst`,
  // `Reasoner`) over the structural `Sequential` we'd see if we asked
  // the backend's runtime metadata. The detail record already carries
  // the user-facing name so we use that as the source of truth.
  const className = detail.class_name ?? meta.data?.class_name ?? "Agent";
  const showTraining = detail.is_trainer || (meta.data?.trainable_paths.length ?? 0) > 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <GroupChrome
        hashContent={hashContent}
        className={className}
        showTraining={showTraining}
        stateTone={detail.running > 0 ? "live" : detail.errors > 0 ? "error" : "ok"}
        stateLabel={detail.running > 0 ? "live" : detail.errors > 0 ? "error" : "ended"}
      />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}

function GroupChrome({
  hashContent,
  className,
  showTraining,
  stateTone,
  stateLabel,
}: {
  hashContent: string;
  className: string;
  showTraining: boolean;
  stateTone: "live" | "error" | "ok";
  stateLabel: string;
}) {
  return (
    <header className="flex h-9 flex-shrink-0 items-center gap-3 border-b border-border bg-bg-1/60 px-2">
      <nav className="flex h-full min-w-0 items-center" aria-label="agent instance sections">
        {agentGroupTabs(hashContent, { showTraining }).map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end ?? false}
            className={({ isActive }) =>
              cn(
                "relative flex h-9 items-center gap-1.5 px-3 text-[12px] font-medium transition-colors",
                "after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:rounded-t-full after:transition-colors",
                isActive
                  ? "text-text after:bg-accent"
                  : "text-muted hover:text-text after:bg-transparent",
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <div className="ml-auto flex min-w-0 items-center gap-2 text-[12px]" aria-label="agent path">
        <Link to="/agents" className="text-muted transition-colors hover:text-text">
          Agents
        </Link>
        <ChevronRight aria-hidden size={12} className="flex-shrink-0 text-muted-2" />
        <span className="truncate text-muted" title={className}>
          {className}
        </span>
        <ChevronRight aria-hidden size={12} className="flex-shrink-0 text-muted-2" />
        <span className="max-w-32 truncate font-mono text-[11px] text-text" title={hashContent}>
          {truncateMiddle(hashContent, 14)}
        </span>
        <HashTag hash={hashContent} mono size="sm" />
        <Pill tone={stateTone} pulse={stateTone === "live"} size="sm">
          {stateLabel}
        </Pill>
      </div>
    </header>
  );
}
