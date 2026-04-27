import { type GroupTreeRow, GroupTreeSection } from "@/components/ui";
import { useOPRORuns } from "@/hooks/use-runs";
import type { AlgorithmGroup, RunSummary } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

export function OPROTree({ search }: { search: string }) {
  const { runId: activeRunId } = useParams();
  const navigate = useNavigate();
  const groups = useOPRORuns();

  const filtered = useMemo(() => {
    if (!groups.data) return [] as AlgorithmGroup[];
    const q = search.trim().toLowerCase();
    if (!q) return groups.data;
    return groups.data
      .map((group) => ({
        ...group,
        runs: group.runs.filter((run) => {
          const hay = [
            group.class_name ?? "",
            run.run_id,
            run.script ?? "",
            paramPaths(run).join(" "),
          ]
            .join(" ")
            .toLowerCase();
          return hay.includes(q);
        }),
      }))
      .filter((group) => group.runs.length > 0);
  }, [groups.data, search]);

  const onSelect = (row: GroupTreeRow) => {
    navigate(`/opro/${row.id}`);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-auto">
        {groups.isLoading ? (
          <div className="p-3 text-xs text-muted">loading OPRO runs...</div>
        ) : (
          <>
            {filtered.map((group) => (
              <GroupTreeSection
                key={group.algorithm_path}
                label="OPRO"
                count={group.count}
                rows={group.runs.map((run) => buildOPRORow(run, activeRunId ?? null))}
                onSelect={onSelect}
              />
            ))}
            {filtered.length === 0 ? (
              <div className="p-3 text-xs text-muted-2">no OPRO runs</div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function buildOPRORow(run: RunSummary, activeRunId: string | null): GroupTreeRow {
  const state = run.state === "running" ? "running" : run.state === "error" ? "error" : "ended";
  const best = bestScore(run);
  const params = paramPaths(run);

  return {
    id: run.run_id,
    colorIdentity: run.run_id,
    label: <span className="font-mono text-[11px]">{truncateMiddle(run.run_id, 14)}</span>,
    meta:
      params.length > 0
        ? `${formatRelativeTime(run.started_at)} · ${params.join(", ")}`
        : formatRelativeTime(run.started_at),
    state,
    trailing: best != null ? best.toFixed(3) : undefined,
    active: activeRunId === run.run_id,
  };
}

function bestScore(run: RunSummary): number | null {
  const scores = run.iterations
    .map((iteration) => iteration.score)
    .filter((score): score is number => typeof score === "number");
  return scores.length > 0 ? Math.max(...scores) : run.algorithm_terminal_score;
}

function paramPaths(run: RunSummary): string[] {
  const paths = new Set<string>();
  for (const iteration of run.iterations) {
    const value = iteration.metadata.param_path;
    if (typeof value === "string" && value.length > 0) paths.add(value);
  }
  return [...paths];
}
