import { GroupTreeSection, Pager, type GroupTreeRow } from "@/components/ui";
import { useAlgorithmGroups } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { SidebarFilters } from "./types";

const PAGE_SIZE = 25;

export function AlgorithmsTree({
  search,
  filters,
}: {
  search: string;
  filters: SidebarFilters;
}) {
  const { runId: activeRunId } = useParams();
  const navigate = useNavigate();
  const groups = useAlgorithmGroups();
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!groups.data) return [] as RunSummary[];
    const q = search.trim().toLowerCase();
    const runs = groups.data.flatMap((group) =>
      group.runs.map((run) => ({
        ...run,
        algorithm_class: run.algorithm_class ?? group.class_name ?? run.algorithm_class,
      })),
    );
    return runs
      .filter((run) => withinTime(run.last_event_at, filters.timeRange))
      .filter((run) => filters.state === "all" || run.state === filters.state)
      .filter((run) => filters.className === "all" || run.algorithm_class === filters.className)
      .filter((run) => filters.script === "all" || run.script === filters.script)
      .filter((run) => {
        if (!q) return true;
        const hay = [run.algorithm_class ?? "", run.run_id, run.script ?? ""]
          .join(" ")
          .toLowerCase();
        return hay.includes(q);
      });
  }, [groups.data, search, filters]);

  const paged = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  const rows = useMemo(
    () => paged.map((run) => buildAlgorithmRow(run, activeRunId ?? null)),
    [paged, activeRunId],
  );

  const onSelect = (row: GroupTreeRow) => {
    navigate(`/algorithms/${row.id}`);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-auto">
        {groups.isLoading ? (
          <div className="p-3 text-xs text-muted">loading algorithms…</div>
        ) : (
          <GroupTreeSection
            label="Algorithms"
            count={filtered.length}
            rows={rows}
            onSelect={onSelect}
            empty="no algorithm runs"
            hideHeader
          />
        )}
      </div>
      {filtered.length > PAGE_SIZE ? (
        <Pager
          page={page}
          pageSize={PAGE_SIZE}
          total={filtered.length}
          onPageChange={setPage}
        />
      ) : null}
    </div>
  );
}

function withinTime(epochSeconds: number, range: SidebarFilters["timeRange"]): boolean {
  if (range === "all") return true;
  const seconds = range === "1h" ? 3600 : 86_400;
  return Date.now() / 1000 - epochSeconds <= seconds;
}

function buildAlgorithmRow(r: RunSummary, activeRunId: string | null): GroupTreeRow {
  const state =
    r.state === "running" ? "running" : r.state === "error" ? "error" : "ended";
  const trailing =
    r.algorithm_terminal_score != null
      ? r.algorithm_terminal_score.toFixed(3)
      : r.event_total > 0
        ? `${r.event_total} ev`
        : undefined;
  const className = r.algorithm_class ?? "Algorithm";
  return {
    id: r.run_id,
    colorIdentity: className,
    label: <span className="text-text">{className}</span>,
    meta: (
      <span className="font-mono text-[10px] text-muted-2">
        {truncateMiddle(r.run_id, 12)} · {formatRelativeTime(r.started_at)}
      </span>
    ),
    state,
    trailing,
    active: activeRunId === r.run_id,
  };
}
