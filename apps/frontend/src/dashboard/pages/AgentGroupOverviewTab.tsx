import { AgentGroupIdentityCard } from "@/components/agent-view/group/identity-card";
import {
  Metric,
  MetricSeriesChart,
  PanelCard,
  PanelSection,
  type RunRow,
  RunTable,
  type RunTableColumn,
} from "@/components/ui";
import { useAgentGroup, useAgentMeta } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/utils";
import { Link, useParams } from "react-router-dom";

const recentColumns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", width: 80 },
  { id: "run", label: "Run", source: "_id", width: "1fr" },
  { id: "started", label: "Started", source: "_started", width: 90 },
  { id: "latency", label: "Latency", source: "_duration", align: "right", width: 90 },
  { id: "cost", label: "Cost", source: "cost", align: "right", width: 80 },
];

export function AgentGroupOverviewTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  const latestRun = group.data?.runs.at(-1) ?? null;
  const meta = useAgentMeta(latestRun?.run_id ?? null, latestRun?.root_agent_path ?? null);

  if (!hashContent || !group.data) return null;
  const detail = group.data;
  const runs = [...detail.runs].sort((a, b) => a.started_at - b.started_at);
  const recent = runs.slice(-5).reverse();
  const successRate = detail.count > 0 ? Math.max(0, 1 - detail.errors / detail.count) : 0;
  const latencyP50 = median(detail.latencies);
  const totalTokens = detail.prompt_tokens + detail.completion_tokens;

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto space-y-4">
        <AgentGroupIdentityCard group={detail} meta={meta.data} />
        <PanelSection label="Activity">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2">
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
        </PanelSection>
        <PanelCard title="Latency x invocation" eyebrow="p50 reference" bodyMinHeight={250}>
          <MetricSeriesChart
            points={metricPoints(runs, "latency")}
            identity={hashContent}
            height={220}
            formatY={(n) => formatDurationMs(n)}
            reference={latencyP50 != null ? { y: latencyP50, label: "group p50" } : undefined}
            xLabel="invocation"
            yLabel="latency"
          />
        </PanelCard>
        <PanelSection
          label="Recent runs"
          count={recent.length}
          toolbar={
            <Link to={`/agents/${hashContent}/runs`} className="text-[12px] text-accent">
              View all {detail.count}
            </Link>
          }
        >
          <RunTable
            rows={recent.map((run) => runRow(run, hashContent))}
            columns={recentColumns}
            storageKey={`agent-group-recent:${hashContent}`}
            rowHref={(row) => `/agents/${hashContent}/runs/${row.id}`}
            pageSize={5}
          />
        </PanelSection>
      </div>
    </div>
  );
}

function metricPoints(runs: RunSummary[], kind: "latency") {
  return runs.map((run, index) => ({
    x: index + 1,
    y: kind === "latency" ? run.duration_ms : null,
    runId: run.run_id,
  }));
}

function runRow(run: RunSummary, hashContent: string): RunRow {
  return {
    id: run.run_id,
    identity: run.hash_content ?? hashContent,
    state: run.state,
    startedAt: run.started_at,
    endedAt: run.last_event_at,
    durationMs: run.duration_ms,
    fields: {
      cost: { kind: "num", value: run.cost?.cost_usd ?? null, format: "cost" },
    },
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
