import { GroupTreeSection, Pager, type GroupTreeRow } from "@/components/ui";
import { useAlgorithmGroups } from "@/hooks/use-runs";
import type { AlgorithmGroup, RunSummary } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const PAGE_SIZE = 25;

/**
 * Sidebar tree for the Algorithms rail.
 *   group  — algorithm class (Beam / Sweep / Debate / EvoGradient / SelfRefine / AutoResearcher)
 *   row    — one orchestrator invocation
 *   child  — synthetic inner agent invocations, on demand
 */
export function AlgorithmsTree({ search }: { search: string }) {
  const { runId: activeRunId } = useParams();
  const navigate = useNavigate();
  const groups = useAlgorithmGroups();
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!groups.data) return [] as AlgorithmGroup[];
    const q = search.trim().toLowerCase();
    if (!q) return groups.data;
    return groups.data
      .map((g) => ({
        ...g,
        runs: g.runs.filter((r) => {
          const hay = [g.class_name ?? "", r.run_id, r.script ?? ""].join(" ").toLowerCase();
          return hay.includes(q);
        }),
      }))
      .filter((g) => g.runs.length > 0);
  }, [groups.data, search]);

  const onSelect = (row: GroupTreeRow) => {
    navigate(`/algorithms/${row.id}`);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-auto">
        {groups.isLoading ? (
          <div className="p-3 text-xs text-muted">loading algorithms…</div>
        ) : (
          <>
            {filtered.map((g) => (
              <AlgorithmGroupSection
                key={g.algorithm_path}
                group={g}
                page={page}
                onPageChange={setPage}
                pageSize={PAGE_SIZE}
                activeRunId={activeRunId ?? null}
                onSelect={onSelect}
              />
            ))}
            {filtered.length === 0 ? (
              <div className="p-3 text-xs text-muted-2">no algorithm runs</div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function AlgorithmGroupSection({
  group,
  page,
  pageSize,
  onPageChange,
  activeRunId,
  onSelect,
}: {
  group: AlgorithmGroup;
  page: number;
  pageSize: number;
  onPageChange: (p: number) => void;
  activeRunId: string | null;
  onSelect: (row: GroupTreeRow) => void;
}) {
  const slice = group.runs.slice(page * pageSize, page * pageSize + pageSize);
  const rows: GroupTreeRow[] = slice.map((r) => buildAlgorithmRow(r, activeRunId));
  return (
    <div>
      <GroupTreeSection
        label={group.class_name ?? "Algorithm"}
        count={group.count}
        rows={rows}
        onSelect={onSelect}
      />
      {group.count > pageSize ? (
        <Pager
          page={page}
          pageSize={pageSize}
          total={group.count}
          onPageChange={onPageChange}
        />
      ) : null}
    </div>
  );
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
  return {
    id: r.run_id,
    colorIdentity: r.run_id,
    label: <span className="font-mono text-[11px]">{truncateMiddle(r.run_id, 14)}</span>,
    meta: r.script
      ? `${formatRelativeTime(r.started_at)} · ${r.script}`
      : formatRelativeTime(r.started_at),
    state,
    trailing,
    active: activeRunId === r.run_id,
  };
}
