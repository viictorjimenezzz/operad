import {
  Breadcrumb,
  EmptyState,
  PanelCard,
  PanelGrid,
  Sparkline,
  StatusDot,
} from "@/components/ui";
import { useAgentGroups } from "@/hooks/use-runs";
import { hashColor } from "@/lib/hash-color";
import type { AgentGroupSummary } from "@/lib/types";
import { formatCost, formatDurationMs, formatRelativeTime, formatTokens } from "@/lib/utils";
import { Link } from "react-router-dom";

export function AgentsIndexPage() {
  const groups = useAgentGroups();

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Agents" }]} />
      <div className="flex-1 overflow-auto p-4">
        {groups.isLoading ? (
          <div className="text-xs text-muted">loading agents…</div>
        ) : !groups.data || groups.data.length === 0 ? (
          <EmptyState
            title="no agents yet"
            description="run an agent or replay a cassette to populate this view"
          />
        ) : (
          <PanelGrid cols={3}>
            {groups.data.map((g) => (
              <AgentGroupCard key={g.hash_content} group={g} />
            ))}
          </PanelGrid>
        )}
      </div>
    </div>
  );
}

function AgentGroupCard({ group }: { group: AgentGroupSummary }) {
  const totalTokens = group.prompt_tokens + group.completion_tokens;
  const avgLatency = group.latencies.length
    ? group.latencies.reduce((a, b) => a + b, 0) / group.latencies.length
    : null;
  return (
    <Link to={`/agents/${group.hash_content}`} className="block">
      <PanelCard
        eyebrow={
          <span className="flex items-center gap-1.5">
            <StatusDot
              identity={group.hash_content}
              state={group.running > 0 ? "running" : group.errors > 0 ? "error" : "ended"}
              size="sm"
            />
            <span>{group.is_trainer ? "Trainer" : "Agent"}</span>
          </span>
        }
        title={group.class_name ?? "Agent"}
        toolbar={
          <span className="rounded-full bg-bg-3 px-2 py-0.5 text-[10px] tabular-nums text-muted-2">
            {group.count}
          </span>
        }
      >
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3 text-[12px]">
            <Stat label="last seen" value={formatRelativeTime(group.last_seen)} />
            <Stat label="avg latency" value={formatDurationMs(avgLatency)} />
            <Stat label="errors" value={group.errors > 0 ? String(group.errors) : "0"} />
            <Stat label="tokens" value={formatTokens(totalTokens)} />
            <Stat label="cost" value={formatCost(group.cost_usd)} />
            <Stat label="running" value={group.running > 0 ? String(group.running) : "—"} />
          </div>
          {group.latencies.length >= 2 ? (
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-[0.06em] text-muted-2">
                latency
              </span>
              <Sparkline
                values={group.latencies.slice(-24)}
                width={200}
                height={28}
                color={hashColor(group.hash_content)}
              />
            </div>
          ) : null}
        </div>
      </PanelCard>
    </Link>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-[0.06em] text-muted-2">{label}</span>
      <span className="font-mono tabular-nums text-text">{value}</span>
    </div>
  );
}
