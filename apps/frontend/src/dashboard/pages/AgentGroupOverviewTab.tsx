import { AgentGroupIdentityCard } from "@/components/agent-view/group/identity-card";
import { DefinitionPanel } from "@/components/agent-view/overview/definition-section";
import { Metric, MultiSeriesChart, PanelCard } from "@/components/ui";
import { type HashKey, HashRow } from "@/components/ui/hash-row";
import { useAgentGroup, useAgentMeta } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/utils";
import { useState } from "react";
import { useParams } from "react-router-dom";

type ToggleKey = "latency" | "cost" | "tokens";

const SERIES_COLORS: Record<ToggleKey, string> = {
  latency: "var(--qual-1)",
  cost: "var(--qual-3)",
  tokens: "var(--qual-5)",
};

export function AgentGroupOverviewTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const latestRun = group.data?.runs.at(-1) ?? null;
  const meta = useAgentMeta(latestRun?.run_id ?? null, latestRun?.root_agent_path ?? null);
  const [visible, setVisible] = useState<Set<ToggleKey>>(new Set(["latency", "cost", "tokens"]));

  if (!hashContent || !group.data) return null;
  const detail = group.data;
  const runs = [...detail.runs].sort((a, b) => a.started_at - b.started_at);
  const N = runs.length;
  const successRate = detail.count > 0 ? Math.max(0, 1 - detail.errors / detail.count) : 0;
  const latencyP50 = median(detail.latencies);
  const totalTokens = detail.prompt_tokens + detail.completion_tokens;

  function toggleMetric(key: ToggleKey) {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const singleRun = N === 1 ? runs[0] : undefined;

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto space-y-4">
        <AgentGroupIdentityCard group={detail} meta={meta.data} />
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border pb-3">
          <Metric label="runs" value={detail.count} />
          <Metric label="ok" value={`${Math.round(successRate * 100)}%`} />
          <Metric label="p50" value={formatDurationMs(latencyP50)} />
          <Metric label="tokens" value={formatTokens(totalTokens)} />
          <Metric label="cost" value={formatCost(detail.cost_usd)} />
          <Metric
            label="state"
            value={detail.running > 0 ? "live" : detail.errors > 0 ? "error" : "ended"}
          />
        </div>
        {N >= 2 ? (
          <PanelCard title="Invocation series" eyebrow="per-invocation" bodyMinHeight={250}>
            <div className="mb-2 flex gap-2">
              {(["latency", "cost", "tokens"] as ToggleKey[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleMetric(key)}
                  className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                    visible.has(key)
                      ? "bg-accent/15 text-accent"
                      : "bg-bg-2 text-muted hover:text-text"
                  }`}
                >
                  {key}
                </button>
              ))}
            </div>
            <MultiSeriesChart
              series={buildSeries(runs, visible)}
              height={220}
              xLabel="invocation"
            />
          </PanelCard>
        ) : null}
        {singleRun ? (
          <div className="space-y-3">
            <DefinitionPanel dataSummary={singleRun} runId={singleRun.run_id} />
            <HashRow current={hashesForRun(singleRun)} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

function buildSeries(runs: RunSummary[], visible: Set<ToggleKey>) {
  const defs: Array<{ key: ToggleKey; getValue: (r: RunSummary) => number | null }> = [
    { key: "latency", getValue: (r) => r.duration_ms },
    { key: "cost", getValue: (r) => r.cost?.cost_usd ?? null },
    {
      key: "tokens",
      getValue: (r) =>
        r.prompt_tokens || r.completion_tokens ? r.prompt_tokens + r.completion_tokens : null,
    },
  ];
  return defs
    .filter((d) => visible.has(d.key))
    .map((d) => ({
      id: d.key,
      label: d.key,
      color: SERIES_COLORS[d.key],
      points: runs.map((run, index) => ({ x: index + 1, y: d.getValue(run) })),
    }));
}

function hashesForRun(run: RunSummary): Partial<Record<HashKey, string | null>> {
  return {
    hash_content: run.hash_content ?? null,
    hash_model: run.hash_model ?? null,
    hash_prompt: run.hash_prompt ?? null,
    hash_input: run.hash_input ?? null,
    hash_output_schema: run.hash_output_schema ?? null,
    hash_graph: run.hash_graph ?? null,
    hash_config: run.hash_config ?? null,
  };
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? (sorted[mid] ?? null)
    : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
}
