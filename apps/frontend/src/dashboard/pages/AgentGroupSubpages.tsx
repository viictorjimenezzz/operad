import {
  EmptyState,
  MultiSeriesChart,
  PanelCard,
  PanelGrid,
  PanelSection,
  StatusDot,
  type MultiSeries,
} from "@/components/ui";
import { useAgentGroup } from "@/hooks/use-runs";
import type { RunSummary } from "@/lib/types";
import { formatCost, formatDurationMs, formatRelativeTime, formatTokens, truncateMiddle } from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

/* ---------- Invocations table tab ---------- */

export function AgentGroupRunsTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  if (!group.data) return null;
  const runs = group.data.runs;
  return (
    <div className="h-full overflow-auto p-4">
      <PanelCard flush>
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-border text-[10px] uppercase tracking-[0.06em] text-muted-2">
              <th className="px-3 py-2 text-left font-medium" />
              <th className="px-3 py-2 text-left font-medium">Run</th>
              <th className="px-3 py-2 text-left font-medium">Started</th>
              <th className="px-3 py-2 text-right font-medium">Latency</th>
              <th className="px-3 py-2 text-right font-medium">Tokens</th>
              <th className="px-3 py-2 text-right font-medium">Cost</th>
              <th className="px-3 py-2 text-right font-medium" />
            </tr>
          </thead>
          <tbody>
            {runs.slice().reverse().map((r) => (
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
                <td className="px-3 py-2 text-right font-mono tabular-nums">{formatDurationMs(r.duration_ms)}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">
                  {formatTokens(r.prompt_tokens + r.completion_tokens)}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">
                  {formatCost(r.cost?.cost_usd ?? 0)}
                </td>
                <td className="px-3 py-2 text-right">
                  <Link
                    to={`/agents/${hashContent}/runs/${r.run_id}`}
                    className="inline-flex items-center gap-1 text-accent hover:text-[--color-accent-strong]"
                  >
                    open
                    <ExternalLink size={11} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </PanelCard>
    </div>
  );
}

/* ---------- Cost / latency comparisons ---------- */

export function AgentGroupCostTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  if (!group.data) return null;
  const runs = group.data.runs;
  const costSeries = useScatter(runs, "cost", "latency");
  const tokensSeries = useScatter(runs, "tokens", "latency");
  return (
    <div className="h-full overflow-auto p-4">
      <PanelSection label="Cost vs latency">
        <PanelGrid cols={2}>
          <PanelCard title="Cost vs latency" eyebrow="USD vs ms" bodyMinHeight={260}>
            <MultiSeriesChart
              series={costSeries}
              height={240}
              formatX={(v) => formatDurationMs(v)}
              formatY={(v) => formatCost(v)}
              xLabel="latency"
              yLabel="cost"
            />
          </PanelCard>
          <PanelCard title="Tokens vs latency" eyebrow="tokens vs ms" bodyMinHeight={260}>
            <MultiSeriesChart
              series={tokensSeries}
              height={240}
              formatX={(v) => formatDurationMs(v)}
              formatY={(v) => formatTokens(v)}
              xLabel="latency"
              yLabel="tokens"
            />
          </PanelCard>
        </PanelGrid>
      </PanelSection>
    </div>
  );
}

function useScatter(
  runs: RunSummary[],
  yKind: "cost" | "tokens",
  xKind: "latency",
): MultiSeries[] {
  return useMemo(() => {
    return runs.map((r) => {
      const x = r.duration_ms;
      const y = yKind === "cost" ? r.cost?.cost_usd ?? 0 : r.prompt_tokens + r.completion_tokens;
      return { id: r.run_id, label: truncateMiddle(r.run_id, 14), points: [{ x, y }] };
    });
  }, [runs, yKind, xKind]);
}

/* ---------- Drift placeholder ---------- */

export function AgentGroupDriftTab() {
  const { hashContent } = useParams<{ hashContent: string }>();
  const group = useAgentGroup(hashContent);
  if (!group.data) return null;
  return (
    <div className="h-full overflow-auto p-4">
      <EmptyState
        title="no drift events recorded"
        description="prompt drift is captured per-Trainer; once a training run for this instance lands here you'll see the per-epoch hash deltas overlaid."
      />
    </div>
  );
}
