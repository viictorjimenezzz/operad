import { Button, type GroupTreeRow, GroupTreeSection } from "@/components/ui";
import { useTrainingGroups } from "@/hooks/use-runs";
import type { RunSummary, TrainingGroup as TrainingGroupT } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import type { SidebarFilters } from "./types";

/**
 * Sidebar tree for the Training rail.
 *   group  — trained agent identity (root hash_content)
 *   row    — Trainer.fit() invocation under that identity
 */
export function TrainingTree({
  search,
  filters,
}: {
  search: string;
  filters: SidebarFilters;
}) {
  const { runId: activeRunId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const groups = useTrainingGroups();
  const [compareMode, setCompareMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    const ids = parseCompare(searchParams.get("compare"));
    if (ids.length > 0) {
      setCompareMode(true);
      setSelected(new Set(ids));
    }
  }, [searchParams]);

  const filtered = useMemo(() => {
    if (!groups.data) return [] as TrainingGroupT[];
    const q = search.trim().toLowerCase();
    return groups.data
      .map((g) => ({
        ...g,
        runs: g.runs.filter((r) => {
          if (!withinTime(r.last_event_at, filters.timeRange)) return false;
          if (filters.state !== "all" && r.state !== filters.state) return false;
          if (filters.algorithm !== "all" && g.algorithm_path !== filters.algorithm) return false;
          const trainee = g.class_name ?? g.root_agent_path ?? "";
          if (filters.trainee !== "all" && trainee !== filters.trainee) return false;
          if (!q) return true;
          const hay = [trainee, g.hash_content ?? "", r.run_id, g.algorithm_path ?? ""]
            .join(" ")
            .toLowerCase();
          return hay.includes(q);
        }),
      }))
      .filter((g) => g.runs.length > 0);
  }, [groups.data, search, filters]);

  const onSelect = (row: GroupTreeRow) => {
    if (compareMode) {
      setSelected((current) => {
        const next = new Set(current);
        if (next.has(row.id)) next.delete(row.id);
        else next.add(row.id);
        return next;
      });
      return;
    }
    navigate(`/training/${row.id}`);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-border p-2">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={compareMode ? "primary" : "ghost"}
            onClick={() => setCompareMode((value) => !value)}
          >
            Compare
          </Button>
          {compareMode ? (
            <>
              <span className="font-mono text-[11px] text-muted">{selected.size} selected</span>
              <Button
                size="sm"
                variant="ghost"
                disabled={selected.size < 2}
                onClick={() =>
                  navigate(`/training?compare=${[...selected].map(encodeURIComponent).join(",")}`)
                }
              >
                Open
              </Button>
            </>
          ) : null}
        </div>
      </div>
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
                selected={selected}
                compareMode={compareMode}
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

function withinTime(epochSeconds: number, range: SidebarFilters["timeRange"]): boolean {
  if (range === "all") return true;
  const seconds = range === "1h" ? 3600 : 86_400;
  return Date.now() / 1000 - epochSeconds <= seconds;
}

function TrainingGroupSection({
  group,
  activeRunId,
  selected,
  compareMode,
  onSelect,
}: {
  group: TrainingGroupT;
  activeRunId: string | null;
  selected: Set<string>;
  compareMode: boolean;
  onSelect: (row: GroupTreeRow) => void;
}) {
  const rows: GroupTreeRow[] = group.runs.map((r) =>
    buildTrainingRow(r, activeRunId, selected, compareMode),
  );
  return (
    <GroupTreeSection
      label={group.class_name ?? "Trainer"}
      count={group.count}
      rows={rows}
      onSelect={onSelect}
    />
  );
}

function buildTrainingRow(
  r: RunSummary,
  activeRunId: string | null,
  selected: Set<string>,
  compareMode: boolean,
): GroupTreeRow {
  const state = r.state === "running" ? "running" : r.state === "error" ? "error" : "ended";
  const lastBatch = r.batches.length > 0 ? r.batches[r.batches.length - 1] : null;
  const epoch = lastBatch?.epoch != null ? `epoch ${lastBatch.epoch}` : null;
  const trailing = compareMode
    ? selected.has(r.run_id)
      ? "selected"
      : "select"
    : (epoch ??
      (r.algorithm_terminal_score != null ? r.algorithm_terminal_score.toFixed(3) : undefined));
  return {
    id: r.run_id,
    colorIdentity: r.run_id,
    label: <span className="font-mono text-[11px]">{truncateMiddle(r.run_id, 14)}</span>,
    meta: formatRelativeTime(r.started_at),
    state,
    trailing,
    active: compareMode ? selected.has(r.run_id) : activeRunId === r.run_id,
  };
}

function parseCompare(raw: string | null): string[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
