import { GroupTreeSection, Pager, type GroupTreeRow } from "@/components/ui";
import { useAgentGroups } from "@/hooks/use-runs";
import type { AgentGroupSummary } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const PAGE_SIZE = 30;

/**
 * Sidebar tree for the Agents rail. Two levels:
 *   group  — agent instance keyed by `hash_content`
 *   child  — invocation (run_id) under that instance
 *
 * Single-invocation groups collapse into a single row with no
 * expansion arrow. Multi-invocation groups expand to show their
 * invocations indented underneath, mirroring W&B's "Group: …" + child
 * runs layout.
 */
export function AgentsTree({ search }: { search: string }) {
  const { hashContent: activeHash, runId: activeRunId } = useParams();
  const navigate = useNavigate();
  const groups = useAgentGroups();
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!groups.data) return [] as AgentGroupSummary[];
    const q = search.trim().toLowerCase();
    if (!q) return groups.data;
    return groups.data.filter((g) => {
      const hay = [g.class_name ?? "", g.root_agent_path ?? "", g.hash_content]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [groups.data, search]);

  const paged = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  const rows: GroupTreeRow[] = useMemo(
    () =>
      paged.map((g) => buildRow(g, activeHash ?? null, activeRunId ?? null)),
    [paged, activeHash, activeRunId],
  );

  const onSelect = (row: GroupTreeRow) => {
    if (row.id.includes("::run::")) {
      const [hash, runId] = row.id.split("::run::");
      if (hash && runId) navigate(`/agents/${hash}/runs/${runId}`);
      return;
    }
    navigate(`/agents/${row.id}`);
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
          />
        )}
      </div>
      {filtered.length > PAGE_SIZE ? (
        <Pager
          page={page}
          pageSize={PAGE_SIZE}
          total={filtered.length}
          onPageChange={setPage}
        />
      ) : null}
    </div>
  );
}

function buildRow(
  g: AgentGroupSummary,
  activeHash: string | null,
  activeRunId: string | null,
): GroupTreeRow {
  const isActive = activeHash === g.hash_content && !activeRunId;
  const meta = g.is_trainer ? `Trainer · ${formatRelativeTime(g.last_seen)}` : formatRelativeTime(g.last_seen);
  const sparkline = g.latencies.slice(-12);
  const state = g.running > 0 ? "running" : g.errors > 0 ? "error" : "ended";

  if (g.count <= 1) {
    return {
      id: g.hash_content,
      label: g.class_name ?? "Agent",
      meta,
      colorIdentity: g.hash_content,
      sparkline,
      state,
      active: isActive,
      count: g.count,
    };
  }
  // Multi-invocation: build child rows for each known run id.
  const children: GroupTreeRow[] = g.run_ids.slice(-12).reverse().map((runId) => ({
    id: `${g.hash_content}::run::${runId}`,
    label: <span className="font-mono text-[11px]">{truncateMiddle(runId, 14)}</span>,
    meta: <span>invocation</span>,
    colorIdentity: runId,
    state: "ended",
    active: activeRunId === runId,
  }));
  return {
    id: g.hash_content,
    label: g.class_name ?? "Agent",
    meta,
    colorIdentity: g.hash_content,
    sparkline,
    state,
    active: isActive,
    count: g.count,
    children,
    trailing: g.errors > 0 ? `${g.errors} err` : undefined,
  };
}

