import { ParameterDiffPanel } from "@/components/agent-view/group/parameter-diff-panel";
import {
  MiniChart,
  extractParameterSeries,
} from "@/components/algorithms/trainer/parameter-evolution-multiples";
import { EmptyState, HashTag, Metric, PanelCard, PanelGrid, PanelSection } from "@/components/ui";
import { hashColor } from "@/lib/hash-color";
import { CheckpointEntry, FitnessEntry, RunSummary } from "@/lib/types";
import { formatDurationMs, formatNumber, truncateMiddle } from "@/lib/utils";
import { useQueries } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

interface TrainingComparePanelProps {
  runIds: string[];
}

type CompareRun = {
  runId: string;
  summary: z.infer<typeof RunSummary> | null;
  fitness: z.infer<typeof FitnessRows>;
  checkpoints: z.infer<typeof CheckpointRows>;
};

const FitnessRows = z.array(FitnessEntry);
const CheckpointRows = z.array(CheckpointEntry);

export function TrainingComparePanel({ runIds }: TrainingComparePanelProps) {
  const ids = useMemo(() => [...new Set(runIds)].filter(Boolean), [runIds]);
  const queries = useQueries({
    queries: ids.map((runId) => ({
      queryKey: ["training-compare", runId] as const,
      queryFn: () => fetchCompareRun(runId),
      enabled: ids.length >= 2,
      retry: false,
    })),
  });
  const runs = queries.map((query, index) => query.data ?? emptyRun(ids[index] ?? ""));
  const loading = queries.some((query) => query.isLoading);

  if (ids.length < 2) {
    return (
      <EmptyState
        title="select at least two training runs"
        description="use the training table or sidebar compare mode to build an overlay"
      />
    );
  }

  if (loading) return <div className="text-xs text-muted">loading comparison...</div>;

  return (
    <div className="space-y-4">
      <CompareHeader runs={runs} />
      <PanelCard title="Overlaid loss curves" bodyMinHeight={280}>
        <OverlayChart runs={runs} metric="loss" />
      </PanelCard>
      <PanelCard title="Overlaid LR schedules" bodyMinHeight={240}>
        <OverlayChart runs={runs} metric="lr" />
      </PanelCard>
      <ParameterCompare runs={runs} />
      <FinalStateDiff runs={runs} />
    </div>
  );
}

function CompareHeader({ runs }: { runs: CompareRun[] }) {
  return (
    <PanelGrid cols={runs.length >= 3 ? 3 : 2}>
      {runs.map((run, index) => (
        <PanelCard
          key={run.runId}
          title={`run ${String.fromCharCode(65 + index)}`}
          eyebrow={run.summary?.algorithm_class ?? "Trainer"}
        >
          <div className="space-y-2 text-[12px] text-muted">
            <HashTag hash={run.summary?.hash_content ?? run.runId} mono size="sm" />
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <Metric label="epochs" value={run.checkpoints.length} />
              <Metric label="best" value={formatBest(run)} />
              <Metric label="duration" value={formatDurationMs(run.summary?.duration_ms)} />
            </div>
          </div>
        </PanelCard>
      ))}
    </PanelGrid>
  );
}

function OverlayChart({ runs, metric }: { runs: CompareRun[]; metric: "loss" | "lr" }) {
  const data = mergeSeries(runs, metric);
  if (data.length === 0) {
    return (
      <EmptyState
        title={metric === "loss" ? "no loss data" : "no LR data"}
        description="selected runs have not emitted comparable series"
      />
    );
  }
  return (
    <ResponsiveContainer width="100%" height={metric === "loss" ? 260 : 220}>
      <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="x" stroke="var(--color-muted)" tick={{ fontSize: 11 }} />
        <YAxis stroke="var(--color-muted)" tick={{ fontSize: 11 }} />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            fontSize: 11,
          }}
        />
        {runs.map((run, index) => (
          <Line
            key={run.runId}
            type="monotone"
            dataKey={`run_${index}`}
            name={truncateMiddle(run.runId, 16)}
            stroke={hashColor(run.summary?.hash_content ?? run.runId)}
            strokeWidth={2}
            dot={metric === "loss" ? { r: 2 } : false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function ParameterCompare({ runs }: { runs: CompareRun[] }) {
  const seriesByRun = runs.map((run) => ({
    run,
    series: extractParameterSeries(run.checkpoints),
  }));
  const paths = [
    ...new Set(seriesByRun.flatMap((entry) => entry.series.map((series) => series.path))),
  ].sort();

  if (paths.length === 0) {
    return (
      <PanelSection label="Parameters">
        <EmptyState
          title="no parameter snapshots"
          description="selected runs have no epoch_end parameter snapshots"
        />
      </PanelSection>
    );
  }

  return (
    <PanelSection label="Parameters" count={paths.length}>
      <div className="space-y-3">
        {paths.map((path) => (
          <PanelCard key={path} title={path}>
            <div
              className="grid gap-3"
              style={{
                gridTemplateColumns: `repeat(${Math.max(runs.length, 1)}, minmax(0, 1fr))`,
              }}
            >
              {seriesByRun.map(({ run, series }, index) => {
                const match = series.find((item) => item.path === path);
                return (
                  <div key={run.runId} className="min-w-0">
                    <div className="mb-2 font-mono text-[10px] text-muted">
                      {String.fromCharCode(65 + index)} {truncateMiddle(run.runId, 12)}
                    </div>
                    {match ? (
                      <MiniChart series={match} height={96} />
                    ) : (
                      <div className="rounded border border-border bg-bg-2 p-3 text-xs text-muted">
                        missing
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </PanelCard>
        ))}
      </div>
    </PanelSection>
  );
}

function FinalStateDiff({ runs }: { runs: CompareRun[] }) {
  const first = runs[0];
  const second = runs[1];
  const [path, setPath] = useState<string | null>(null);
  if (!first || !second) return null;
  const left = finalValues(first.checkpoints);
  const right = finalValues(second.checkpoints);
  const paths = [...new Set([...Object.keys(left), ...Object.keys(right)])].sort();
  const active = path && paths.includes(path) ? path : paths[0];

  if (!active) {
    return (
      <PanelCard title="Final-state diff">
        <EmptyState title="no final parameter snapshot" />
      </PanelCard>
    );
  }

  return (
    <PanelCard title="Final-state diff">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted">path</span>
        <select
          value={active}
          onChange={(event) => setPath(event.target.value)}
          className="rounded border border-border bg-bg-2 px-2 py-1 text-text"
        >
          {paths.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <ParameterDiffPanel path={active} previous={left[active]} current={right[active]} />
    </PanelCard>
  );
}

async function fetchCompareRun(runId: string): Promise<CompareRun> {
  const [summaryRaw, fitnessRaw, checkpointsRaw] = await Promise.all([
    fetchJson(`/runs/${encodeURIComponent(runId)}/summary`),
    fetchJson(`/runs/${encodeURIComponent(runId)}/fitness.json`),
    fetchJson(`/runs/${encodeURIComponent(runId)}/checkpoints.json`),
  ]);
  const summary = RunSummary.safeParse(summaryRaw);
  const fitness = FitnessRows.safeParse(fitnessRaw);
  const checkpoints = CheckpointRows.safeParse(checkpointsRaw);
  return {
    runId,
    summary: summary.success ? summary.data : null,
    fitness: fitness.success ? fitness.data : [],
    checkpoints: checkpoints.success ? checkpoints.data : [],
  };
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} <- ${url}`);
  return response.json();
}

function emptyRun(runId: string): CompareRun {
  return { runId, summary: null, fitness: [], checkpoints: [] };
}

function mergeSeries(runs: CompareRun[], metric: "loss" | "lr") {
  const byX = new Map<number, Record<string, number | null>>();
  runs.forEach((run, index) => {
    for (const row of run.fitness) {
      const x = Number(row.gen_index);
      const value = metric === "loss" ? (row.train_loss ?? row.best) : (row.lr ?? null);
      if (value == null || !Number.isFinite(value)) continue;
      const existing = byX.get(x) ?? { x };
      existing[`run_${index}`] = value;
      byX.set(x, existing);
    }
  });
  return [...byX.values()].sort((a, b) => Number(a.x) - Number(b.x));
}

function finalValues(checkpoints: z.infer<typeof CheckpointRows>): Record<string, unknown> {
  const last = [...checkpoints]
    .filter((checkpoint) => checkpoint.parameter_snapshot)
    .sort((a, b) => a.epoch - b.epoch)
    .at(-1);
  return last?.parameter_snapshot ?? {};
}

function formatBest(run: CompareRun): string {
  const scores = [
    run.summary?.algorithm_terminal_score,
    ...run.checkpoints.map((checkpoint) => checkpoint.score),
  ].filter((value): value is number => value != null && Number.isFinite(value));
  return scores.length === 0 ? "-" : formatNumber(Math.max(...scores));
}
