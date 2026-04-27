import { TrainingComparePanel } from "@/components/algorithms/trainer/training-compare-panel";
import {
  Breadcrumb,
  Button,
  EmptyState,
  Metric,
  PanelSection,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";
import { useTrainingGroups } from "@/hooks/use-runs";
import type { RunSummary, TrainingGroup } from "@/lib/types";
import { formatDurationMs, formatNumber } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 80 },
  { id: "class", label: "Trainee class", source: "class", sortable: true, width: "1fr" },
  { id: "hash", label: "Hash", source: "hash", sortable: true, width: 116 },
  { id: "runs", label: "# runs", source: "runs", sortable: true, align: "right", width: 72 },
  {
    id: "best",
    label: "Best score",
    source: "best",
    sortable: true,
    align: "right",
    width: 88,
  },
  {
    id: "epochs",
    label: "Last epochs",
    source: "epochs",
    sortable: true,
    align: "right",
    width: 92,
  },
  { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 84 },
  { id: "spark", label: "Loss", source: "spark", width: 84 },
];

export function TrainingIndexPage() {
  const groups = useTrainingGroups();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [selected, setSelected] = useState<string[]>([]);
  const compareIds = parseCompare(searchParams.get("compare"));
  const data = groups.data ?? [];
  const rows = useMemo(() => data.map(groupRow), [data]);
  const stats = useMemo(() => trainingStats(data), [data]);

  if (compareIds.length >= 2) {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <Breadcrumb
          items={[{ label: "Training", to: "/training" }, { label: "Compare" }]}
          trailing={
            <Button size="sm" variant="ghost" onClick={() => navigate("/training")}>
              Back to table
            </Button>
          }
        />
        <div className="flex-1 overflow-auto p-4">
          <TrainingComparePanel runIds={compareIds} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Training" }]} />
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading trainings...</div>
        ) : rows.length === 0 ? (
          <EmptyState
            title="no training runs yet"
            description="kick off a Trainer.fit() to see loss curves, drift timelines, and gradient logs here"
          />
        ) : (
          <div className="space-y-4">
            <PanelSection
              label="Training"
              toolbar={
                selected.length >= 2 ? (
                  <Button
                    size="sm"
                    onClick={() =>
                      navigate(`/training?compare=${selected.map(encodeURIComponent).join(",")}`)
                    }
                  >
                    Compare
                  </Button>
                ) : null
              }
            >
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2">
                <Metric label="trainee instances" value={stats.trainees} />
                <Metric label="training runs" value={stats.runs} />
                <Metric
                  label="best score"
                  value={stats.bestScore == null ? "-" : formatNumber(stats.bestScore)}
                />
                <Metric label="total epochs run" value={stats.epochs} />
                <Metric label="total wall" value={formatDurationMs(stats.wallMs)} />
              </div>
            </PanelSection>
            <RunTable
              rows={rows}
              columns={columns}
              storageKey="training-index"
              rowHref={(row) => `/training/${row.id}`}
              selectable
              onSelectionChange={setSelected}
              emptyTitle="no training runs yet"
              emptyDescription="Trainer.fit() runs appear here grouped by trainee hash"
            />
          </div>
        )}
      </div>
    </div>
  );
}

function groupRow(group: TrainingGroup): RunRow {
  const runs = [...group.runs].sort((a, b) => a.started_at - b.started_at);
  const latest = runs.at(-1);
  const identity = group.hash_content ?? latest?.run_id ?? "pending";
  const state = group.running > 0 ? "running" : group.errors > 0 ? "error" : "ended";
  const best = bestScore(runs);
  return {
    id: latest?.run_id ?? identity,
    identity,
    state,
    startedAt: group.first_seen,
    endedAt: group.last_seen,
    durationMs: runs.reduce((acc, run) => acc + run.duration_ms, 0),
    fields: {
      class: { kind: "text", value: group.class_name ?? "Trainer" },
      hash: group.hash_content
        ? { kind: "hash", value: group.hash_content }
        : { kind: "text", value: "pending", mono: true },
      runs: { kind: "num", value: group.count, format: "int" },
      best: { kind: "num", value: best, format: "score" },
      epochs: { kind: "num", value: latest ? epochCount(latest) : null, format: "int" },
      cost: {
        kind: "num",
        value: runs.reduce((acc, run) => acc + (run.cost?.cost_usd ?? 0), 0),
        format: "cost",
      },
      spark: { kind: "sparkline", values: lossSeries(runs).slice(-24) },
    },
  };
}

function trainingStats(groups: TrainingGroup[]) {
  const runs = groups.flatMap((group) => group.runs);
  return {
    trainees: groups.length,
    runs: runs.length,
    bestScore: bestScore(runs),
    epochs: runs.reduce((acc, run) => acc + epochCount(run), 0),
    wallMs: runs.reduce((acc, run) => acc + run.duration_ms, 0),
  };
}

function parseCompare(raw: string | null): string[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function bestScore(runs: RunSummary[]): number | null {
  const scores = runs
    .flatMap((run) => [run.algorithm_terminal_score, run.metrics?.best_score, run.metrics?.score])
    .filter((score): score is number => score != null && Number.isFinite(score));
  return scores.length > 0 ? Math.max(...scores) : null;
}

function epochCount(run: RunSummary): number {
  const epochEnds = run.iterations.filter((item) => item.phase === "epoch_end").length;
  if (epochEnds > 0) return epochEnds;
  const epochs = run.batches
    .map((batch) => batch.epoch)
    .filter((epoch): epoch is number => epoch != null);
  return epochs.length > 0 ? new Set(epochs).size : 0;
}

function lossSeries(runs: RunSummary[]): Array<number | null> {
  return runs.map((run) => {
    const losses = run.iterations
      .map((item) => item.metadata.train_loss)
      .filter((value): value is number => typeof value === "number");
    return losses.at(-1) ?? run.algorithm_terminal_score ?? null;
  });
}
