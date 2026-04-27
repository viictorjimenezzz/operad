import { Breadcrumb, EmptyState, PanelCard, PanelGrid, StatusDot } from "@/components/ui";
import { useTrainingGroups } from "@/hooks/use-runs";
import type { TrainingGroup } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";
import { Link } from "react-router-dom";

export function TrainingIndexPage() {
  const groups = useTrainingGroups();
  const total = groups.data?.reduce((acc, g) => acc + g.count, 0) ?? 0;
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Training" }]} />
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading trainings…</div>
        ) : total === 0 ? (
          <EmptyState
            title="no training runs yet"
            description="kick off a Trainer.fit() to see loss curves, drift timelines, and gradient logs here"
          />
        ) : (
          <div className="space-y-4">
            {groups.data?.map((g) => (
              <TrainingGroupBlock
                key={g.hash_content ?? g.runs[0]?.run_id ?? "_unknown"}
                group={g}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TrainingGroupBlock({ group }: { group: TrainingGroup }) {
  const head = group.runs[group.runs.length - 1];
  return (
    <PanelCard
      eyebrow={
        <span className="flex items-center gap-1.5">
          <StatusDot identity={group.hash_content ?? head?.run_id ?? ""} size="sm" />
          <span>Trainer</span>
        </span>
      }
      title={
        <span>
          {group.class_name ?? "Trainer"}
          <span className="ml-2 rounded-full bg-bg-3 px-2 py-0.5 text-[10px] tabular-nums text-muted-2">
            {group.count}
          </span>
        </span>
      }
    >
      <PanelGrid cols={3}>
        {group.runs.slice().reverse().slice(0, 12).map((r) => (
          <Link to={`/training/${r.run_id}`} key={r.run_id} className="block">
            <PanelCard surface="inset" bare flush className="px-3 py-2.5 hover:border-border-strong">
              <div className="flex items-center gap-2">
                <StatusDot
                  identity={r.run_id}
                  state={r.state === "running" ? "running" : r.state === "error" ? "error" : "ended"}
                  size="sm"
                />
                <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-text">
                  {r.run_id}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-2">
                <span>{formatRelativeTime(r.started_at)}</span>
                {r.algorithm_terminal_score != null ? (
                  <span className="ml-auto font-mono tabular-nums text-text">
                    {r.algorithm_terminal_score.toFixed(3)}
                  </span>
                ) : null}
              </div>
            </PanelCard>
          </Link>
        ))}
      </PanelGrid>
    </PanelCard>
  );
}
