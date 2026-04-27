import { agentGroupTabs } from "@/components/agent-view/page-shell/agent-group-tabs";
import { Breadcrumb, type BreadcrumbItem, EmptyState, HashTag, Pill } from "@/components/ui";
import { useAgentGroup, useAgentMeta } from "@/hooks/use-runs";
import { truncateMiddle } from "@/lib/utils";
import { NavLink, Outlet, useParams } from "react-router-dom";

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
  const className = detail.class_name ?? "Agent";
  const showTrain =
    detail.is_trainer ||
    (meta.data?.trainable_paths.length ?? 0) > 0 ||
    detail.runs.some((run) => run.metrics?.best_score != null);
  const breadcrumbs: BreadcrumbItem[] = [
    { label: "Agents", to: "/agents" },
    { label: className },
    { label: truncateMiddle(hashContent, 14), mono: true },
  ];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb
        items={breadcrumbs}
        trailing={
          <>
            <HashTag hash={hashContent} mono size="sm" />
            <Pill
              tone={detail.running > 0 ? "live" : detail.errors > 0 ? "error" : "ok"}
              pulse={detail.running > 0}
            >
              {detail.running > 0 ? "live" : detail.errors > 0 ? "error" : "ended"}
            </Pill>
          </>
        }
      />
      <GroupTabs hashContent={hashContent} showTrain={showTrain} />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}

function GroupTabs({ hashContent, showTrain }: { hashContent: string; showTrain: boolean }) {
  return (
    <div className="flex h-9 items-center border-b border-border bg-bg-1/60 px-2">
      {agentGroupTabs(hashContent, { showTrain }).map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end ?? false}
          className={({ isActive }) =>
            `relative flex h-9 items-center gap-1.5 px-3 text-[12px] font-medium transition-colors ${
              isActive
                ? "text-text after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:bg-accent"
                : "text-muted hover:text-text"
            }`
          }
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  );
}
