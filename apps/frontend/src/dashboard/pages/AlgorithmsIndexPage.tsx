import { Breadcrumb, EmptyState, PanelCard, PanelGrid, StatusDot } from "@/components/ui";
import { useAlgorithmGroups } from "@/hooks/use-runs";
import type { AlgorithmGroup } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";
import { Link } from "react-router-dom";

export function AlgorithmsIndexPage() {
  const groups = useAlgorithmGroups();
  const allRuns = groups.data?.flatMap((g) => g.runs) ?? [];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Algorithms" }]} />
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading algorithms…</div>
        ) : allRuns.length === 0 ? (
          <EmptyState
            title="no algorithm runs yet"
            description="run a Beam / Sweep / Debate / EvoGradient / SelfRefine / AutoResearcher script to populate this view"
          />
        ) : (
          <div className="space-y-4">
            {groups.data?.map((g) => (
              <AlgorithmGroupBlock key={g.algorithm_path} group={g} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AlgorithmGroupBlock({ group }: { group: AlgorithmGroup }) {
  return (
    <PanelCard
      eyebrow="Algorithm"
      title={
        <span>
          {group.class_name ?? group.algorithm_path}
          <span className="ml-2 rounded-full bg-bg-3 px-2 py-0.5 text-[10px] tabular-nums text-muted-2">
            {group.count}
          </span>
        </span>
      }
    >
      <PanelGrid cols={3}>
        {group.runs.slice().reverse().slice(0, 12).map((r) => (
          <Link to={`/algorithms/${r.run_id}`} key={r.run_id} className="block">
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
              {r.script ? (
                <div className="mt-1 truncate font-mono text-[10px] text-muted-2" title={r.script}>
                  {r.script}
                </div>
              ) : null}
            </PanelCard>
          </Link>
        ))}
      </PanelGrid>
    </PanelCard>
  );
}
