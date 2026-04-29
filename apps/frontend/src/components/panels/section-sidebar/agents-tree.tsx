import { type GroupTreeRow, GroupTreeSection, Pager } from "@/components/ui";
import { useAgentGroups } from "@/hooks/use-runs";
import type { AgentGroupSummary } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { SidebarFilters } from "./types";

const PAGE_SIZE = 30;

export function AgentsTree({
  search,
  filters,
}: {
  search: string;
  filters: SidebarFilters;
}) {
  const { hashContent: activeHash, runId: activeRunId } = useParams<{
    hashContent?: string;
    runId?: string;
  }>();
  const navigate = useNavigate();
  const groups = useAgentGroups();
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!groups.data) return [] as AgentGroupSummary[];
    const q = search.trim().toLowerCase();
    return groups.data
      .filter((instance) => withinTime(instance.last_seen, filters.timeRange))
      .filter((instance) => filters.state === "all" || groupState(instance) === filters.state)
      .filter((instance) => filters.className === "all" || instance.class_name === filters.className)
      .filter((instance) => filters.backend === "all" || instance.backends.includes(filters.backend))
      .filter((instance) => filters.model === "all" || instance.models.includes(filters.model))
      .filter((instance) =>
        filters.invocationCount === "single"
          ? instance.count === 1
          : filters.invocationCount === "multi"
            ? instance.count > 1
            : true,
      )
      .filter((instance) => {
        if (!q) return true;
        const hay = [
          instance.class_name ?? "",
          instance.root_agent_path ?? "",
          instance.hash_content,
          ...instance.run_ids,
          ...instance.backends,
          ...instance.models,
        ]
          .join(" ")
          .toLowerCase();
        return hay.includes(q);
      })
      .sort((a, b) => b.last_seen - a.last_seen);
  }, [groups.data, search, filters]);

  const paged = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  const rows: GroupTreeRow[] = useMemo(
    () => paged.map((group) => buildInstanceRow(group, activeHash ?? null, activeRunId ?? null)),
    [paged, activeHash, activeRunId],
  );

  const onSelect = (row: GroupTreeRow) => {
    if (row.id.startsWith("run::")) {
      const payload = row.id.slice("run::".length);
      const splitAt = payload.indexOf("::");
      const hashContent = splitAt >= 0 ? payload.slice(0, splitAt) : "";
      const runId = splitAt >= 0 ? payload.slice(splitAt + 2) : "";
      if (hashContent && runId) navigate(`/agents/${hashContent}/runs/${runId}`);
      return;
    }
    if (row.id.startsWith("instance::")) {
      const hashContent = row.id.slice("instance::".length);
      navigate(`/agents/${hashContent}`);
      return;
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-auto">
        {groups.isLoading ? (
          <div className="p-3 text-xs text-muted">loading agents…</div>
        ) : (
          <GroupTreeSection
            label="Instances"
            count={filtered.length}
            rows={rows}
            onSelect={onSelect}
            empty="no agents yet"
            hideHeader
          />
        )}
      </div>
      {filtered.length > PAGE_SIZE ? (
        <Pager page={page} pageSize={PAGE_SIZE} total={filtered.length} onPageChange={setPage} />
      ) : null}
    </div>
  );
}

function withinTime(epochSeconds: number, range: SidebarFilters["timeRange"]): boolean {
  if (range === "all") return true;
  const seconds = range === "1h" ? 3600 : 86_400;
  return Date.now() / 1000 - epochSeconds <= seconds;
}

function groupState(group: AgentGroupSummary): SidebarFilters["state"] {
  if (group.running > 0) return "running";
  if (group.errors > 0) return "error";
  return "ended";
}

function buildInstanceRow(
  g: AgentGroupSummary,
  activeHash: string | null,
  activeRunId: string | null,
): GroupTreeRow {
  const isActive = activeHash === g.hash_content && !activeRunId;
  const meta = <span className="font-mono text-[10px]">{truncateMiddle(g.hash_content, 16)}</span>;
  // Only show a sparkline when there are at least two latency samples;
  // otherwise the Sparkline component would render a line that looks like
  // an unrelated divider in the sidebar.
  const finiteLatencies = g.latencies.filter((value) => Number.isFinite(value));
  const firstLatency = finiteLatencies[0];
  const hasLatencyShape =
    firstLatency != null && finiteLatencies.some((value) => value !== firstLatency);
  const sparkline = hasLatencyShape ? g.latencies.slice(-12) : undefined;
  const state = g.running > 0 ? "running" : g.errors > 0 ? "error" : "ended";
  const children: GroupTreeRow[] = g.run_ids
    .slice()
    .reverse()
    .map((runId) => ({
      id: `run::${g.hash_content}::${runId}`,
      label: <span className="font-mono text-[11px]">{truncateMiddle(runId, 14)}</span>,
      meta: <span>invocation</span>,
      colorIdentity: g.hash_content,
      state: "ended",
      active: activeHash === g.hash_content && activeRunId === runId,
    }));
  const trailing =
    g.errors > 0
      ? `${g.errors} err`
      : sparkline === undefined
        ? `${g.count} invocation${g.count === 1 ? "" : "s"}`
        : undefined;
  return {
    id: `instance::${g.hash_content}`,
    label: g.class_name ?? "Agent",
    meta,
    colorIdentity: g.hash_content,
    ...(sparkline ? { sparkline } : {}),
    state,
    active: isActive,
    count: g.count,
    children,
    ...(trailing ? { trailing } : {}),
  };
}
