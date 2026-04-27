import { agentGroupTabs } from "@/components/agent-view/page-shell/agent-group-tabs";
import {
  Breadcrumb,
  EmptyState,
  HashTag,
  MultiSeriesChart,
  PanelCard,
  PanelGrid,
  PanelSection,
  Pill,
  StatusDot,
  type MultiSeries,
} from "@/components/ui";
import { useAgentGroup } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import {
  formatCost,
  formatDurationMs,
  formatRelativeTime,
  formatTokens,
  truncateMiddle,
} from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";

/**
 * The Agent Group page — what a user sees when they click on a multi-
 * invoked instance in the sidebar. Shows KPIs aggregated across the
 * whole group and per-run multi-series charts colored by run_id.
 *
 * Routes:
 *   /agents/:hashContent          -> overview (this default tab)
 *   /agents/:hashContent/runs     -> table of runs
 *   /agents/:hashContent/metrics  -> per-run metric comparisons
 *   /agents/:hashContent/train    -> trainable parameter series
 *   /agents/:hashContent/graph    -> group graph
 */
export function AgentGroupPage() {
  const { hashContent } = useParams<{ hashContent: string }>();
  if (!hashContent) return <EmptyState title="missing hash" />;
  return <AgentGroupPageInner hashContent={hashContent} />;
}

function AgentGroupPageInner({ hashContent }: { hashContent: string }) {
  const group = useAgentGroup(hashContent);
  if (group.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted">
        loading group…
      </div>
    );
  }
  if (group.error || !group.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState title="group not found" description="this hash_content is no longer in the registry" />
      </div>
    );
  }

  const detail = group.data;
  const className = detail.class_name ?? "Agent";

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb
        items={[
          { label: "Agents", to: "/agents" },
          { label: className },
          { label: truncateMiddle(hashContent, 14), mono: true },
        ]}
        trailing={
          <>
            <HashTag hash={hashContent} mono size="sm" />
            <Pill tone={detail.running > 0 ? "live" : "ok"} pulse={detail.running > 0}>
              {detail.running > 0 ? "live" : "ended"}
            </Pill>
          </>
        }
      />
      <GroupTabs hashContent={hashContent} />
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}

function GroupTabs({ hashContent }: { hashContent: string }) {
  return (
    <div className="flex h-9 items-center border-b border-border bg-bg-1/60 px-2">
      {agentGroupTabs(hashContent).map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end ?? false}
          className={({ isActive }) =>
            `relative flex h-9 items-center gap-1.5 px-3 text-[12px] font-medium transition-colors ${
              isActive
                ? "text-text after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:bg-accent"
                : "text-muted hover:text-text"
            }`
          }
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  );
}

// --- Tabs ---

export function AgentGroupOverviewTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  if (!hashContent) return null;
  return <AgentGroupOverviewInner hashContent={hashContent} />;
}

function AgentGroupOverviewInner({ hashContent }: { hashContent: string }) {
  const group = useAgentGroup(hashContent);
  const data = group.data;
  if (!data) return null;
  const runs = data.runs;

  const totalTokens = data.prompt_tokens + data.completion_tokens;
  const avgLatency = data.latencies.length
    ? data.latencies.reduce((a, b) => a + b, 0) / data.latencies.length
    : null;
  const errorRate = data.count > 0 ? (data.errors / data.count) * 100 : 0;

  const latencySeries = useRunSeries(runs, "latency");
  const tokensSeries = useRunSeries(runs, "tokens");
  const costSeries = useRunSeries(runs, "cost");

  return (
    <div className="h-full overflow-auto p-4">
      <PanelSection label="Summary">
        <PanelGrid cols={4} gap="md">
          <Kpi label="Runs" value={String(data.count)} />
          <Kpi
            label="Success rate"
            value={`${Math.max(0, 100 - errorRate).toFixed(1)}%`}
            {...(data.errors > 0 ? { sub: `${data.errors} errors` } : {})}
          />
          <Kpi label="Avg latency" value={formatDurationMs(avgLatency)} />
          <Kpi label="Total tokens" value={formatTokens(totalTokens)} />
          <Kpi label="Cost" value={formatCost(data.cost_usd)} />
          <Kpi label="Last seen" value={formatRelativeTime(data.last_seen)} />
          <Kpi label="First seen" value={formatRelativeTime(data.first_seen)} />
          <Kpi label="Live" value={data.running > 0 ? String(data.running) : "0"} />
        </PanelGrid>
      </PanelSection>

      <div className="my-4" />

      <PanelSection label="Charts" count={3}>
        <PanelGrid cols={3}>
          <PanelCard title="Latency" eyebrow="ms · per run" bodyMinHeight={220}>
            <MultiSeriesChart series={latencySeries} height={200} formatY={(n) => `${Math.round(n)}ms`} />
          </PanelCard>
          <PanelCard title="Tokens" eyebrow="prompt + completion" bodyMinHeight={220}>
            <MultiSeriesChart series={tokensSeries} height={200} formatY={(n) => formatTokens(n)} />
          </PanelCard>
          <PanelCard title="Cost (USD)" eyebrow="per invocation" bodyMinHeight={220}>
            <MultiSeriesChart series={costSeries} height={200} formatY={(n) => formatCost(n)} />
          </PanelCard>
        </PanelGrid>
      </PanelSection>

      <div className="my-4" />

      <PanelSection label="Invocations" count={data.count}>
        <PanelCard flush>
          <RunsTable runs={runs} hashContent={hashContent} />
        </PanelCard>
      </PanelSection>
    </div>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <PanelCard surface="inset" bare flush className="px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.06em] text-muted-2">{label}</div>
      <div className="text-[15px] font-semibold tabular-nums text-text">{value}</div>
      {sub ? <div className="text-[10px] text-muted-2">{sub}</div> : null}
    </PanelCard>
  );
}

function useRunSeries(runs: RunSummary[], kind: "latency" | "tokens" | "cost"): MultiSeries[] {
  return useMemo(() => {
    return runs.map((r, i) => {
      const point =
        kind === "latency"
          ? r.duration_ms
          : kind === "tokens"
            ? r.prompt_tokens + r.completion_tokens
            : r.cost?.cost_usd ?? 0;
      return {
        id: r.run_id,
        label: truncateMiddle(r.run_id, 14),
        points: [{ x: i + 1, y: point }],
      };
    });
  }, [runs, kind]);
}

function RunsTable({ runs, hashContent }: { runs: RunSummary[]; hashContent: string }) {
  return (
    <table className="w-full text-[12px]">
      <thead>
        <tr className="border-b border-border text-[10px] uppercase tracking-[0.06em] text-muted-2">
          <th className="px-3 py-2 text-left font-medium">State</th>
          <th className="px-3 py-2 text-left font-medium">Run</th>
          <th className="px-3 py-2 text-left font-medium">Started</th>
          <th className="px-3 py-2 text-right font-medium">Latency</th>
          <th className="px-3 py-2 text-right font-medium">Tokens</th>
          <th className="px-3 py-2 text-right font-medium">Cost</th>
          <th className="px-3 py-2 text-right font-medium" />
        </tr>
      </thead>
      <tbody>
        {runs.slice().reverse().map((r) => {
          const tokens = r.prompt_tokens + r.completion_tokens;
          return (
            <tr key={r.run_id} className="border-b border-border/60 transition-colors hover:bg-bg-2">
              <td className="px-3 py-2">
                <StatusDot
                  identity={r.run_id}
                  state={r.state === "running" ? "running" : r.state === "error" ? "error" : "ended"}
                  size="sm"
                />
              </td>
              <td className="px-3 py-2 font-mono text-text">{truncateMiddle(r.run_id, 16)}</td>
              <td className="px-3 py-2 text-muted">{formatRelativeTime(r.started_at)}</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">
                {formatDurationMs(r.duration_ms)}
              </td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">
                {formatTokens(tokens)}
              </td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">
                {formatCost(r.cost?.cost_usd ?? 0)}
              </td>
              <td className="px-3 py-2 text-right">
                <NavLink
                  to={`/agents/${hashContent}/runs/${r.run_id}`}
                  className="inline-flex items-center gap-1 text-accent hover:text-[--color-accent-strong]"
                >
                  open
                  <ExternalLink size={11} />
                </NavLink>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
