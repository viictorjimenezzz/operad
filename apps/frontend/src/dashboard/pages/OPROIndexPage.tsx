import {
  Breadcrumb,
  EmptyState,
  type RunRow,
  RunTable,
  type RunTableColumn,
  StatTile,
} from "@/components/ui";
import { useOPRORuns } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
  { id: "params", label: "Param targeted", source: "params", sortable: true, width: "1fr" },
  { id: "hash", label: "hash", source: "hash", sortable: true, width: 120 },
  {
    id: "proposals",
    label: "# proposals",
    source: "proposals",
    sortable: true,
    align: "right",
    width: 96,
  },
  {
    id: "accepted",
    label: "# accepted",
    source: "accepted",
    sortable: true,
    align: "right",
    width: 92,
  },
  {
    id: "best",
    label: "best score",
    source: "best",
    sortable: true,
    align: "right",
    width: 92,
  },
  { id: "last", label: "last seen", source: "_ended", sortable: true, width: 110 },
  { id: "cost", label: "cost", source: "cost", sortable: true, align: "right", width: 78 },
  { id: "sparkline", label: "sparkline", source: "sparkline", width: 82 },
];

export function OPROIndexPage() {
  const groups = useOPRORuns();
  const runs = groups.data?.flatMap((group) => group.runs) ?? [];
  const rows = runs.map((run) => runToRow(run));
  const kpis = summarizeRuns(runs);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "OPRO" }]} />
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading OPRO runs...</div>
        ) : runs.length === 0 ? (
          <EmptyState
            title="no OPRO runs yet"
            description="OPRO optimizer sessions will appear here once they emit algorithm events"
          />
        ) : (
          <div className="space-y-4">
            <div className="grid gap-3 rounded-lg border border-border bg-bg-1 p-3 md:grid-cols-5">
              <StatTile label="OPRO sessions" value={kpis.total} size="sm" />
              <StatTile label="currently active" value={kpis.running} size="sm" />
              <StatTile
                label="best score"
                value={kpis.bestScore == null ? "-" : kpis.bestScore.toFixed(3)}
                size="sm"
              />
              <StatTile label="total proposals" value={kpis.proposals} size="sm" />
              <StatTile label="acceptance rate" value={`${kpis.acceptanceRate}%`} size="sm" />
            </div>
            <RunTable
              rows={rows}
              columns={columns}
              storageKey="opro-index"
              rowHref={(row) => `/opro/${encodeURIComponent(row.id)}`}
              emptyTitle="no OPRO sessions"
              emptyDescription="run an OPRO optimizer session to populate this table"
              pageSize={50}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function runToRow(run: RunSummary): RunRow {
  const params = paramPaths(run);
  const scores = evaluateScores(run);
  const accepted = run.iterations.filter((iteration) => iteration.metadata.accepted === true);
  const identity = run.hash_content ?? run.run_id;

  return {
    id: run.run_id,
    identity,
    state: run.state,
    startedAt: run.started_at,
    endedAt: run.last_event_at,
    durationMs: run.duration_ms,
    fields: {
      params: { kind: "text", value: params.length > 0 ? params.join(", ") : "-", mono: true },
      hash: { kind: "hash", value: identity },
      proposals: { kind: "num", value: proposalCount(run), format: "int" },
      accepted: { kind: "num", value: accepted.length, format: "int" },
      best: { kind: "num", value: bestScore(run), format: "score" },
      cost: { kind: "num", value: run.cost?.cost_usd ?? null, format: "cost" },
      sparkline: { kind: "sparkline", values: scores },
    },
  };
}

function summarizeRuns(runs: RunSummary[]) {
  const proposals = runs.reduce((sum, run) => sum + proposalCount(run), 0);
  const accepted = runs.reduce(
    (sum, run) =>
      sum + run.iterations.filter((iteration) => iteration.metadata.accepted === true).length,
    0,
  );
  const bestScores = runs
    .map((run) => bestScore(run))
    .filter((score): score is number => score != null);
  const acceptanceRate = proposals > 0 ? Math.round((accepted / proposals) * 100) : 0;

  return {
    total: runs.length,
    running: runs.filter((run) => run.state === "running").length,
    bestScore: bestScores.length > 0 ? Math.max(...bestScores) : null,
    proposals,
    accepted,
    acceptanceRate,
  };
}

function proposalCount(run: RunSummary): number {
  const proposeCount = run.iterations.filter((iteration) => iteration.phase === "propose").length;
  if (proposeCount > 0) return proposeCount;
  return run.iterations.filter((iteration) => iteration.phase === "evaluate").length;
}

function evaluateScores(run: RunSummary): number[] {
  return run.iterations
    .filter((iteration) => iteration.phase === "evaluate" || iteration.score != null)
    .map((iteration) => iteration.score)
    .filter((score): score is number => typeof score === "number");
}

function bestScore(run: RunSummary): number | null {
  const scores = evaluateScores(run);
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
