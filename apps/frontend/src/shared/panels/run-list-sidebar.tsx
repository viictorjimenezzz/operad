import { useRuns } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { formatDurationMs, formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Chip } from "@/shared/ui/chip";
import { EmptyState } from "@/shared/ui/empty-state";
import { useUIStore } from "@/stores/ui";
import { Link, useParams } from "react-router-dom";

export function RunListSidebar() {
  const { data: runs, isLoading } = useRuns();
  const filter = useUIStore((s) => s.runListFilter);
  const setFilter = useUIStore((s) => s.setRunListFilter);
  const { runId: currentRunId } = useParams();

  const filtered = (runs ?? []).filter((r) => {
    if (filter === "algorithms") return r.is_algorithm;
    if (filter === "agents") return !r.is_algorithm;
    return true;
  });

  return (
    <aside className="flex h-full flex-col border-r border-border bg-bg-1">
      <div className="border-b border-border px-3 py-2">
        <h2 className="m-0 mb-2 text-[0.72rem] uppercase tracking-[0.1em] text-muted">runs</h2>
        <div className="flex flex-wrap gap-1">
          <Chip active={filter === "all"} onClick={() => setFilter("all")}>
            all
          </Chip>
          <Chip active={filter === "algorithms"} onClick={() => setFilter("algorithms")}>
            algorithms
          </Chip>
          <Chip active={filter === "agents"} onClick={() => setFilter("agents")}>
            agents
          </Chip>
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {isLoading && <div className="p-3 text-xs text-muted">loading…</div>}
        {!isLoading && filtered.length === 0 && (
          <EmptyState title="no runs yet" description="run a demo to populate this list" />
        )}
        <ul>
          {filtered.map((r) => (
            <RunRow key={r.run_id} run={r} active={r.run_id === currentRunId} />
          ))}
        </ul>
      </div>
    </aside>
  );
}

function RunRow({ run, active }: { run: RunSummary; active: boolean }) {
  return (
    <li>
      <Link
        to={`/runs/${run.run_id}`}
        className={`block border-b border-border/60 px-3 py-2 transition-colors hover:bg-bg-2 ${
          active ? "bg-bg-2" : ""
        }`}
      >
        <div className="flex items-center justify-between gap-2 text-[11px]">
          <span className="font-mono text-text">{truncateMiddle(run.run_id, 14)}</span>
          <Badge
            variant={run.state === "running" ? "live" : run.state === "error" ? "error" : "ended"}
          >
            {run.state}
          </Badge>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-muted">
          <span>{run.algorithm_path ?? run.root_agent_path ?? "—"}</span>
          <span className="font-mono">
            {run.duration_ms > 0
              ? formatDurationMs(run.duration_ms)
              : formatRelativeTime(run.started_at)}
          </span>
        </div>
      </Link>
    </li>
  );
}
