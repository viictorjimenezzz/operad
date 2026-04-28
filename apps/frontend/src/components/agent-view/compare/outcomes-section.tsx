import { CompareRunColumn } from "@/components/agent-view/compare/compare-run-column";
import { CompareSection } from "@/components/agent-view/compare/compare-section";
import type { CompareRun } from "@/components/agent-view/compare/types";
import { formatCost, formatDurationMs, formatNumber, formatTokens } from "@/lib/utils";

export function OutcomesSection({ runs }: { runs: CompareRun[] }) {
  const reference = runs[0] ?? null;
  const referenceLatency = latency(reference);
  const referenceCost = cost(reference);
  const referenceTokens = tokens(reference);
  const referenceScore = score(reference);

  return (
    <CompareSection title="Outcomes">
      <div
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${Math.max(1, runs.length)}, minmax(0, 1fr))` }}
      >
        {runs.map((run, index) => {
          const currentLatency = latency(run);
          const currentCost = cost(run);
          const currentTokens = tokens(run);
          const currentScore = score(run);
          return (
            <CompareRunColumn key={run.runId} run={run}>
              <MetricRow
                label="latency"
                value={formatDurationMs(currentLatency)}
                delta={index === 0 ? null : delta(currentLatency, referenceLatency)}
              />
              <MetricRow
                label="cost"
                value={formatCost(currentCost)}
                delta={index === 0 ? null : delta(currentCost, referenceCost)}
              />
              <MetricRow
                label="tokens"
                value={formatTokens(currentTokens)}
                delta={index === 0 ? null : delta(currentTokens, referenceTokens)}
              />
              <MetricRow
                label="score"
                value={formatNumber(currentScore)}
                delta={index === 0 ? null : delta(currentScore, referenceScore)}
              />
            </CompareRunColumn>
          );
        })}
      </div>
    </CompareSection>
  );
}

function MetricRow({ label, value, delta }: { label: string; value: string; delta: number | null }) {
  const tone = delta == null ? "text-muted" : delta > 0 ? "text-[--color-ok]" : "text-[--color-err]";
  return (
    <div className="flex items-baseline justify-between border-b border-border pb-1 text-[11px] last:border-b-0">
      <span className="text-muted">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-text">{value}</span>
        {delta == null ? null : <span className={`font-mono text-[10px] ${tone}`}>{signed(delta)}</span>}
      </div>
    </div>
  );
}

function signed(value: number): string {
  if (!Number.isFinite(value) || value === 0) return "±0";
  return `${value > 0 ? "+" : ""}${formatNumber(value)}`;
}

function latency(run: CompareRun | null): number | null {
  if (!run) return null;
  return run.latestInvocation?.latency_ms ?? run.summary.duration_ms ?? null;
}

function cost(run: CompareRun | null): number | null {
  if (!run) return null;
  return run.summary.cost?.cost_usd ?? null;
}

function tokens(run: CompareRun | null): number | null {
  if (!run) return null;
  return run.summary.prompt_tokens + run.summary.completion_tokens;
}

function score(run: CompareRun | null): number | null {
  if (!run) return null;
  if (run.summary.algorithm_terminal_score != null) return run.summary.algorithm_terminal_score;
  const best = run.summary.metrics?.best_score;
  return best != null ? best : null;
}

function delta(value: number | null, base: number | null): number | null {
  if (value == null || base == null) return null;
  return value - base;
}
