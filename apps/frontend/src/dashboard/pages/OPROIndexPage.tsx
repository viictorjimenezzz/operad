import { Breadcrumb, EmptyState, PanelCard, PanelGrid, StatusDot } from "@/components/ui";
import { useAlgorithmGroups } from "@/hooks/use-runs";
import type { AlgorithmGroup } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";
import { Link } from "react-router-dom";

export function OPROIndexPage() {
  const groups = useAlgorithmGroups();
  const oproGroups = groups.data?.filter((group) => isOpro(group)) ?? [];
  const runs = oproGroups.flatMap((group) => group.runs);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "OPRO" }]} />
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading OPRO runs...</div>
        ) : runs.length === 0 ? (
          <EmptyState
            title="no OPRO runs yet"
            description="OPRO optimizer runs will appear here once they emit algorithm events"
          />
        ) : (
          <PanelGrid cols={3}>
            {runs
              .slice()
              .reverse()
              .map((run) => (
                <Link to={`/opro/${run.run_id}`} key={run.run_id} className="block">
                  <PanelCard
                    surface="inset"
                    bare
                    flush
                    className="px-3 py-2.5 hover:border-border-strong"
                  >
                    <div className="flex items-center gap-2">
                      <StatusDot
                        identity={run.run_id}
                        state={
                          run.state === "running"
                            ? "running"
                            : run.state === "error"
                              ? "error"
                              : "ended"
                        }
                        size="sm"
                      />
                      <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-text">
                        {run.run_id}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-2">
                      <span>{formatRelativeTime(run.started_at)}</span>
                      {run.algorithm_terminal_score != null ? (
                        <span className="ml-auto font-mono tabular-nums text-text">
                          {run.algorithm_terminal_score.toFixed(3)}
                        </span>
                      ) : null}
                    </div>
                  </PanelCard>
                </Link>
              ))}
          </PanelGrid>
        )}
      </div>
    </div>
  );
}

function isOpro(group: AlgorithmGroup): boolean {
  const haystack = `${group.algorithm_path} ${group.class_name ?? ""}`.toLowerCase();
  return haystack.includes("opro");
}
