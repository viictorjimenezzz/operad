import { GroupTreeSection, type GroupTreeRow } from "@/components/ui";
import { useTrainingGroups } from "@/hooks/use-runs";
import type { RunSummary, TrainingGroup as TrainingGroupT } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

/**
 * Sidebar tree for the Training rail.
 *   group  — trained agent identity (root hash_content)
 *   row    — Trainer.fit() invocation under that identity
 */
export function TrainingTree({ search }: { search: string }) {
  const { runId: activeRunId } = useParams();
  const navigate = useNavigate();
  const groups = useTrainingGroups();

  const filtered = useMemo(() => {
    if (!groups.data) return [] as TrainingGroupT[];
    const q = search.trim().toLowerCase();
    if (!q) return groups.data;
    return groups.data
      .map((g) => ({
        ...g,
        runs: g.runs.filter((r) => {
          const hay = [g.class_name ?? "", g.hash_content ?? "", r.run_id]
            .join(" ")
            .toLowerCase();
          return hay.includes(q);
        }),
      }))
      .filter((g) => g.runs.length > 0);
  }, [groups.data, search]);

  const onSelect = (row: GroupTreeRow) => {
    navigate(`/training/${row.id}`);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-auto">
        {groups.isLoading ? (
          <div className="p-3 text-xs text-muted">loading trainings…</div>
        ) : (
          <>
            {filtered.map((g) => (
              <TrainingGroupSection
                key={g.hash_content ?? g.runs[0]?.run_id ?? "_unknown"}
                group={g}
                activeRunId={activeRunId ?? null}
                onSelect={onSelect}
              />
            ))}
            {filtered.length === 0 ? (
              <div className="p-3 text-xs text-muted-2">no training runs</div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function TrainingGroupSection({
  group,
  activeRunId,
  onSelect,
}: {
  group: TrainingGroupT;
  activeRunId: string | null;
  onSelect: (row: GroupTreeRow) => void;
}) {
  const rows: GroupTreeRow[] = group.runs.map((r) => buildTrainingRow(r, activeRunId));
  return (
    <GroupTreeSection
      label={group.class_name ?? "Trainer"}
      count={group.count}
      rows={rows}
      onSelect={onSelect}
    />
  );
}

function buildTrainingRow(r: RunSummary, activeRunId: string | null): GroupTreeRow {
  const state =
    r.state === "running" ? "running" : r.state === "error" ? "error" : "ended";
  const lastBatch = r.batches.length > 0 ? r.batches[r.batches.length - 1] : null;
  const epoch = lastBatch?.epoch != null ? `epoch ${lastBatch.epoch}` : null;
  const trailing = epoch ?? (r.algorithm_terminal_score != null
    ? r.algorithm_terminal_score.toFixed(3)
    : undefined);
  return {
    id: r.run_id,
    colorIdentity: r.run_id,
    label: <span className="font-mono text-[11px]">{truncateMiddle(r.run_id, 14)}</span>,
    meta: formatRelativeTime(r.started_at),
    state,
    trailing,
    active: activeRunId === r.run_id,
  };
}
