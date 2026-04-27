import {
  type ChildRunSummary,
  CriticRationaleCard,
} from "@/components/algorithms/beam/critic-rationale-card";
import { EmptyState } from "@/components/ui/empty-state";
import { PanelCard } from "@/components/ui/panel-card";
import { PanelGrid } from "@/components/ui/panel-grid";
import { Sparkline } from "@/components/ui/sparkline";
import { StatusDot } from "@/components/ui/status-dot";
import { Candidate, RunSummary as RunSummarySchema } from "@/lib/types";
import { formatCost, formatDurationMs, formatNumber } from "@/lib/utils";
import { z } from "zod";

const CandidateArray = z.array(Candidate);
const ChildrenArray = z.array(
  RunSummarySchema.passthrough().extend({
    hash_content: z.string().nullable().optional(),
  }),
);

interface BeamDetailOverviewProps {
  dataSummary: unknown;
  dataIterations?: unknown;
  dataChildren?: unknown;
}

export function BeamDetailOverview({
  dataSummary,
  dataIterations,
  dataChildren,
}: BeamDetailOverviewProps) {
  const summary = RunSummarySchema.safeParse(dataSummary);
  if (!summary.success) {
    return <EmptyState title="no beam summary" description="waiting for run summary" />;
  }

  const candidates = CandidateArray.parse(summary.data.candidates ?? []);
  if (candidates.length === 0) {
    return (
      <EmptyState title="no beam candidates" description="beam has not emitted candidates yet" />
    );
  }
  const firstCandidate = candidates[0];
  if (!firstCandidate) {
    return (
      <EmptyState title="no beam candidates" description="beam has not emitted candidates yet" />
    );
  }

  const children = parseChildren(dataChildren);
  const topIndices = parseTopIndices(dataIterations);
  const sorted = [...candidates].sort(
    (a, b) => (b.score ?? Number.NEGATIVE_INFINITY) - (a.score ?? Number.NEGATIVE_INFINITY),
  );
  const winner = sorted.find((candidate) => candidate.score != null) ?? firstCandidate;
  const winnerIndex = winner.candidate_index ?? 0;
  const generatorRun = pairChildren(children).get(winnerIndex)?.generator ?? null;
  const scores = candidates
    .map((candidate) => candidate.score)
    .filter((score): score is number => score != null);
  const threshold =
    topIndices.size > 0
      ? Math.min(
          ...candidates
            .filter(
              (candidate) =>
                candidate.candidate_index != null && topIndices.has(candidate.candidate_index),
            )
            .map((candidate) => candidate.score)
            .filter((score): score is number => score != null),
        )
      : null;

  return (
    <div className="flex flex-col gap-3">
      <PanelCard>
        <div className="flex flex-wrap items-center gap-4 text-[12px] text-muted">
          <span className="inline-flex items-center gap-2">
            <StatusDot state={summary.data.state} />
            <span className="font-mono text-text">{summary.data.state}</span>
          </span>
          <span>
            n=<span className="font-mono text-text">{candidates.length}</span>
          </span>
          <span>
            top_k=<span className="font-mono text-text">{topIndices.size || 1}</span>
          </span>
          <span>
            winner score=
            <span className="font-mono text-text">
              {winner?.score != null ? winner.score.toFixed(3) : "unscored"}
            </span>
          </span>
          <span>
            duration=
            <span className="font-mono text-text">
              {formatDurationMs(summary.data.duration_ms)}
            </span>
          </span>
        </div>
      </PanelCard>

      <CriticRationaleCard
        candidate={winner}
        generatorRun={generatorRun}
        criticRun={pairChildren(children).get(winnerIndex)?.critic ?? null}
        rank={1}
        topK
      />

      <PanelGrid cols={3}>
        <PanelCard title="score band">
          <Sparkline values={scores} height={36} />
          {threshold != null && Number.isFinite(threshold) ? (
            <div className="mt-2 text-[11px] text-muted">
              top-k threshold{" "}
              <span className="font-mono text-[--color-ok]">{threshold.toFixed(3)}</span>
            </div>
          ) : null}
        </PanelCard>
        <Kpi label="score range" value={scoreRange(scores)} />
        <Kpi label="judge cost" value={formatCost(totalCriticCost(children))} />
      </PanelGrid>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <PanelCard title={label}>
      <div className="font-mono text-[20px] text-text">{value}</div>
    </PanelCard>
  );
}

function parseChildren(data: unknown): ChildRunSummary[] {
  const parsed = ChildrenArray.safeParse(data);
  return parsed.success
    ? [...parsed.data].sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0))
    : [];
}

function parseTopIndices(data: unknown): Set<number> {
  if (!data || typeof data !== "object" || Array.isArray(data)) return new Set();
  const rows = (data as Record<string, unknown>).iterations;
  if (!Array.isArray(rows)) return new Set();
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const metadata = (row as Record<string, unknown>).metadata;
    if (!metadata || typeof metadata !== "object") continue;
    const top = (metadata as Record<string, unknown>).top_indices;
    if (Array.isArray(top))
      return new Set(top.filter((value): value is number => typeof value === "number"));
  }
  return new Set();
}

function pairChildren(
  children: ChildRunSummary[],
): Map<number, { generator?: ChildRunSummary; critic?: ChildRunSummary }> {
  const critics = children.filter((child) => isCritic(child));
  const generators = children.filter((child) => !isCritic(child));
  const out = new Map<number, { generator?: ChildRunSummary; critic?: ChildRunSummary }>();
  const count = Math.max(generators.length, critics.length);
  for (let i = 0; i < count; i += 1) {
    out.set(i, {
      ...(generators[i] ? { generator: generators[i] } : {}),
      ...(critics[i] ? { critic: critics[i] } : {}),
    });
  }
  return out;
}

function isCritic(child: ChildRunSummary): boolean {
  const path = `${child.root_agent_path ?? ""} ${child.algorithm_class ?? ""}`.toLowerCase();
  return path.includes("critic") || path.includes("judge") || path.includes("score");
}

function scoreRange(scores: number[]): string {
  if (scores.length === 0) return "unscored";
  return `${formatNumber(Math.min(...scores))}-${formatNumber(Math.max(...scores))}`;
}

function totalCriticCost(children: ChildRunSummary[]): number {
  return children.filter(isCritic).reduce((sum, child) => sum + (child.cost?.cost_usd ?? 0), 0);
}
