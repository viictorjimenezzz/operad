import { CostVsQualityScatter } from "@/components/charts/cost-vs-quality-scatter";
import { CurveOverlay } from "@/components/charts/curve-overlay";
import { MultiPromptDiff } from "@/components/charts/multi-prompt-diff";
import { OperatorRadar } from "@/components/charts/operator-radar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useRuns } from "@/hooks/use-runs";
import { dashboardApi } from "@/lib/api/dashboard";
import type {
  DebateRound,
  FitnessEntry,
  IterationsResponse,
  MutationsMatrix,
  RunSummary,
} from "@/lib/types";
import {
  formatCost,
  formatDurationMs,
  formatNumber,
  formatRelativeTime,
  formatTokens,
  truncateMiddle,
} from "@/lib/utils";
import { useQueries } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

interface RunDetails {
  fitness: FitnessEntry[] | null;
  iterations: IterationsResponse | null;
  debate: DebateRound[] | null;
  mutations: MutationsMatrix | null;
}

interface RunComparisonModel {
  summary: RunSummary;
  curve: Array<{ x: number; y: number }>;
  prompt: string;
  operatorRates: Record<string, number>;
  cost: number;
  quality: number | null;
  label: string;
}

const LOSS_BASED_ALGOS = new Set(["Trainer"]);

export function parseRunsParam(raw: string | null): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const piece of raw.split(",")) {
    const id = piece.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

export function resolveComparisonRunIds(raw: string | null): string[] {
  return parseRunsParam(raw);
}

export function updateRunsSearch(current: URLSearchParams, nextRunIds: string[]): URLSearchParams {
  const next = new URLSearchParams(current);
  if (nextRunIds.length === 0) next.delete("runs");
  else next.set("runs", [...new Set(nextRunIds)].join(","));
  return next;
}

export function computeParetoFrontier(
  points: Array<{ runId: string; cost: number; quality: number }>,
): string[] {
  const sorted = [...points].sort(
    (a, b) => a.cost - b.cost || b.quality - a.quality || a.runId.localeCompare(b.runId),
  );
  const keep: string[] = [];
  let best = Number.NEGATIVE_INFINITY;
  for (const p of sorted) {
    if (p.quality > best) {
      best = p.quality;
      keep.push(p.runId);
    }
  }
  return keep;
}

function agreement(scores: number[]): number {
  if (scores.length < 2) return 1;
  const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
  const variance = scores.reduce((a, s) => a + (s - mean) ** 2, 0) / scores.length;
  return Math.max(0, Math.min(1, 1 - Math.sqrt(variance) / 0.5));
}

export function buildCurve(
  summary: RunSummary,
  details: RunDetails | undefined,
): Array<{ x: number; y: number }> {
  if (summary.algorithm_class === "Debate") {
    const rounds = details?.debate ?? [];
    return rounds.map((r, i) => ({
      x: r.round_index ?? i,
      y: Number(agreement(r.scores).toFixed(3)),
    }));
  }
  const fitness = details?.fitness ?? [];
  return fitness
    .map((f) => ({ x: f.gen_index, y: f.best }))
    .filter((p) => Number.isFinite(p.y))
    .sort((a, b) => a.x - b.x);
}

export function buildOperatorRates(
  mutations: MutationsMatrix | null | undefined,
): Record<string, number> {
  if (!mutations || mutations.ops.length === 0) return {};
  const out: Record<string, number> = {};
  for (let i = 0; i < mutations.ops.length; i++) {
    const op = mutations.ops[i];
    if (!op) continue;
    const attempts = mutations.attempts[i]?.reduce((a, b) => a + b, 0) ?? 0;
    const success = mutations.success[i]?.reduce((a, b) => a + b, 0) ?? 0;
    out[op] = attempts > 0 ? success / attempts : 0;
  }
  return out;
}

function latestIterationText(iterations: IterationsResponse | null | undefined): string {
  const rows = iterations?.iterations ?? [];
  for (let i = rows.length - 1; i >= 0; i--) {
    const text = rows[i]?.text?.trim();
    if (text) return text;
  }
  return "";
}

function bestCandidateText(summary: RunSummary): string {
  const candidates = summary.candidates
    .filter((c) => (c.text ?? "").trim().length > 0)
    .sort((a, b) => (b.score ?? Number.NEGATIVE_INFINITY) - (a.score ?? Number.NEGATIVE_INFINITY));
  return candidates[0]?.text?.trim() ?? "";
}

function debateWinnerText(rounds: DebateRound[] | null | undefined): string {
  if (!rounds || rounds.length === 0) return "";
  const sorted = [...rounds].sort((a, b) => (a.round_index ?? 0) - (b.round_index ?? 0));
  const last = sorted[sorted.length - 1];
  if (!last || last.proposals.length === 0) return "";
  const winnerIdx = last.scores.length > 0 ? last.scores.indexOf(Math.max(...last.scores)) : 0;
  return last.proposals[winnerIdx]?.content?.trim() ?? last.proposals[0]?.content?.trim() ?? "";
}

export function buildPromptText(summary: RunSummary, details: RunDetails | undefined): string {
  const fromIterations = latestIterationText(details?.iterations);
  if (fromIterations) return fromIterations;

  const fromCandidates = bestCandidateText(summary);
  if (fromCandidates) return fromCandidates;

  const fromDebate = debateWinnerText(details?.debate);
  if (fromDebate) return fromDebate;

  return "";
}

export function computeQuality(
  summary: RunSummary,
  curve: Array<{ x: number; y: number }>,
): number | null {
  if (curve.length === 0) return null;
  const lastValue = curve[curve.length - 1]?.y;
  if (lastValue == null || !Number.isFinite(lastValue)) return null;
  if (summary.algorithm_class && LOSS_BASED_ALGOS.has(summary.algorithm_class)) {
    return -lastValue;
  }
  return lastValue;
}

function Sparkline({ points }: { points: Array<{ x: number; y: number }> }) {
  if (points.length < 2) return <span className="text-muted">—</span>;

  const width = 120;
  const height = 26;
  const minY = Math.min(...points.map((p) => p.y));
  const maxY = Math.max(...points.map((p) => p.y));
  const rangeY = maxY - minY || 1;

  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * width;
      const y = height - ((p.y - minY) / rangeY) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-label="sparkline">
      <title>sparkline</title>
      <polyline fill="none" stroke="var(--color-accent)" strokeWidth="1.8" points={path} />
    </svg>
  );
}

async function safeGet<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

async function loadRunDetails(summary: RunSummary): Promise<RunDetails> {
  const algorithm = summary.algorithm_class ?? "";
  const needsDebate = algorithm === "Debate";
  const needsFitness = !needsDebate;

  const [fitness, iterations, debate, mutations] = await Promise.all([
    needsFitness ? safeGet(() => dashboardApi.fitness(summary.run_id)) : Promise.resolve(null),
    safeGet(() => dashboardApi.iterations(summary.run_id)),
    needsDebate ? safeGet(() => dashboardApi.debate(summary.run_id)) : Promise.resolve(null),
    safeGet(() => dashboardApi.mutations(summary.run_id)),
  ]);

  return { fitness, iterations, debate, mutations };
}

export function ExperimentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerQuery, setPickerQuery] = useState("");

  const selectedRunIds = resolveComparisonRunIds(searchParams.get("runs"));

  const allRuns = useRuns();

  const summaryQueries = useQueries({
    queries: selectedRunIds.map((runId) => ({
      queryKey: ["experiments", "summary", runId] as const,
      queryFn: () => dashboardApi.runSummary(runId),
      retry: false,
    })),
  });

  const summaries = summaryQueries
    .filter((q): q is typeof q & { data: RunSummary } => q.isSuccess)
    .map((q) => q.data);

  const detailQueries = useQueries({
    queries: summaries.map((summary) => ({
      queryKey: ["experiments", "details", summary.run_id] as const,
      queryFn: () => loadRunDetails(summary),
      retry: false,
    })),
  });

  const detailsByRunId = useMemo(() => {
    const map = new Map<string, RunDetails>();
    detailQueries.forEach((q, i) => {
      const summary = summaries[i];
      if (!summary || !q.isSuccess) return;
      map.set(summary.run_id, q.data);
    });
    return map;
  }, [detailQueries, summaries]);

  const models = useMemo<RunComparisonModel[]>(() => {
    return summaries.map((summary) => {
      const details = detailsByRunId.get(summary.run_id);
      const curve = buildCurve(summary, details);
      const prompt = buildPromptText(summary, details);
      const operatorRates = buildOperatorRates(details?.mutations);
      const cost = summary.cost?.cost_usd ?? summary.prompt_tokens + summary.completion_tokens;
      const quality = computeQuality(summary, curve);
      const label = `${summary.algorithm_class ?? "Agent"}/${truncateMiddle(summary.run_id, 12)}`;
      return { summary, curve, prompt, operatorRates, cost, quality, label };
    });
  }, [detailsByRunId, summaries]);

  const scatterPoints = models
    .filter((m) => m.quality != null && Number.isFinite(m.cost))
    .map((m) => ({
      runId: m.summary.run_id,
      label: `${m.summary.algorithm_class ?? "Agent"}-${m.summary.run_id.slice(0, 6)}`,
      cost: m.cost,
      quality: m.quality as number,
    }));

  const paretoRunIds = computeParetoFrontier(scatterPoints);

  const curveSeries = models
    .filter((m) => m.curve.length > 0)
    .map((m) => ({ runId: m.summary.run_id, label: m.label, points: m.curve }));

  const isHeterogeneous = new Set(models.map((m) => m.summary.algorithm_class ?? "agent")).size > 1;

  const operatorRuns = models.map((m) => ({
    runId: m.summary.run_id,
    label: m.label,
    operatorRates: m.operatorRates,
  }));

  const promptColumns = models.map((m) => ({
    runId: m.summary.run_id,
    label: m.label,
    text: m.prompt,
  }));

  const loadingSummaries = selectedRunIds.length > 0 && summaryQueries.some((q) => q.isPending);
  const loadingDetails = summaries.length > 0 && detailQueries.some((q) => q.isPending);

  const pickerCandidates = (allRuns.data ?? [])
    .filter((r) => !selectedRunIds.includes(r.run_id))
    .filter((r) => {
      if (!pickerQuery.trim()) return true;
      const hay = [r.run_id, r.algorithm_class ?? "", r.algorithm_path ?? ""]
        .join(" ")
        .toLowerCase();
      return hay.includes(pickerQuery.trim().toLowerCase());
    })
    .slice(0, 20);

  function setRunIds(nextRunIds: string[]) {
    setSearchParams(updateRunsSearch(searchParams, nextRunIds));
  }

  function appendRun(runId: string) {
    setRunIds([...selectedRunIds, runId]);
  }

  if (loadingSummaries || loadingDetails) {
    return <div className="p-4 text-xs text-muted">loading comparison…</div>;
  }

  if (selectedRunIds.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="no runs selected"
          description="cmd-click two or more runs in the sidebar, then click Compare"
          cta={
            <Link
              to="/"
              className="rounded border border-accent bg-accent-dim px-3 py-1.5 text-xs text-text hover:bg-accent/20"
            >
              go to runs
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
        <div>
          <h1 className="m-0 text-sm font-medium uppercase tracking-[0.08em] text-muted">
            experiments — comparing {models.length} run{models.length === 1 ? "" : "s"}
          </h1>
        </div>

        <div className="relative flex items-center gap-2">
          <button
            type="button"
            className="rounded border border-border bg-bg-2 px-2.5 py-1 text-xs text-text hover:bg-bg-3"
            onClick={() => setPickerOpen((v) => !v)}
          >
            Add run
          </button>
          <button
            type="button"
            className="rounded border border-border bg-bg-2 px-2.5 py-1 text-xs text-text hover:bg-bg-3"
            onClick={() => setRunIds([])}
          >
            Clear all
          </button>

          {pickerOpen ? (
            <div className="absolute right-0 top-8 z-20 w-[380px] rounded border border-border bg-bg-1 p-2 shadow-lg">
              <input
                value={pickerQuery}
                onChange={(e) => setPickerQuery(e.target.value)}
                placeholder="search runs…"
                className="mb-2 w-full rounded border border-border bg-bg-2 px-2 py-1 text-xs text-text outline-none"
              />
              <div className="max-h-56 overflow-auto">
                {pickerCandidates.length === 0 ? (
                  <div className="px-2 py-2 text-xs text-muted">no matching runs</div>
                ) : (
                  <ul className="m-0 list-none p-0">
                    {pickerCandidates.map((run) => (
                      <li key={run.run_id}>
                        <button
                          type="button"
                          onClick={() => appendRun(run.run_id)}
                          className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-xs hover:bg-bg-2"
                        >
                          <span className="font-mono text-text">
                            {truncateMiddle(run.run_id, 20)}
                          </span>
                          <span className="text-muted">{run.algorithm_class ?? "Agent"}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>run metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full border-collapse text-[11px]">
            <thead>
              <tr className="border-b border-border text-muted">
                <th className="px-2 py-1 text-left font-medium">run</th>
                <th className="px-2 py-1 text-left font-medium">algorithm</th>
                <th className="px-2 py-1 text-right font-medium">started</th>
                <th className="px-2 py-1 text-right font-medium">duration</th>
                <th className="px-2 py-1 text-right font-medium">tokens</th>
                <th className="px-2 py-1 text-right font-medium">cost</th>
                <th className="px-2 py-1 text-right font-medium">state</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.summary.run_id} className="border-b border-border/60">
                  <td className="px-2 py-1 font-mono text-text">
                    {truncateMiddle(m.summary.run_id, 24)}
                  </td>
                  <td className="px-2 py-1 text-muted">
                    {m.summary.algorithm_class ?? m.summary.algorithm_path ?? "Agent"}
                  </td>
                  <td className="px-2 py-1 text-right text-muted">
                    {formatRelativeTime(m.summary.started_at)}
                  </td>
                  <td className="px-2 py-1 text-right tabular-nums">
                    {formatDurationMs(m.summary.duration_ms)}
                  </td>
                  <td className="px-2 py-1 text-right tabular-nums">
                    {formatTokens(m.summary.prompt_tokens + m.summary.completion_tokens)}
                  </td>
                  <td className="px-2 py-1 text-right tabular-nums">{formatCost(m.cost)}</td>
                  <td className="px-2 py-1 text-right">
                    <span
                      className={
                        m.summary.state === "running"
                          ? "text-accent"
                          : m.summary.state === "error"
                            ? "text-err"
                            : "text-ok"
                      }
                    >
                      {m.summary.state}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {selectedRunIds.length > 5 ? (
        <Card>
          <CardHeader>
            <CardTitle>compact summary</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full border-collapse text-[11px]">
              <thead>
                <tr className="border-b border-border text-muted">
                  <th className="px-2 py-1 text-left font-medium">run</th>
                  <th className="px-2 py-1 text-left font-medium">algorithm</th>
                  <th className="px-2 py-1 text-right font-medium">quality</th>
                  <th className="px-2 py-1 text-right font-medium">cost</th>
                  <th className="px-2 py-1 text-right font-medium">trend</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.summary.run_id} className="border-b border-border/60">
                    <td className="px-2 py-1 font-mono">{truncateMiddle(m.summary.run_id, 24)}</td>
                    <td className="px-2 py-1 text-muted">{m.summary.algorithm_class ?? "Agent"}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{formatNumber(m.quality)}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{formatCost(m.cost)}</td>
                    <td className="px-2 py-1 text-right">
                      <Sparkline points={m.curve} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>curve overlay</CardTitle>
            </CardHeader>
            <CardContent>
              <CurveOverlay series={curveSeries} isHeterogeneous={isHeterogeneous} />
            </CardContent>
          </Card>

          <div className="grid gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>cost vs quality</CardTitle>
              </CardHeader>
              <CardContent>
                <CostVsQualityScatter points={scatterPoints} paretoRunIds={paretoRunIds} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>operator radar</CardTitle>
              </CardHeader>
              <CardContent>
                <OperatorRadar runs={operatorRuns} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>final prompt diff</CardTitle>
            </CardHeader>
            <CardContent>
              <MultiPromptDiff prompts={promptColumns} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
