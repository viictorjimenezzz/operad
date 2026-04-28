import { GroupTreeSection, Pager, type GroupTreeRow } from "@/components/ui";
import { useAgentGroups } from "@/hooks/use-runs";
import type { AgentGroupSummary } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const PAGE_SIZE = 30;

export function AgentsTree({ search }: { search: string }) {
  const {
    hashContent: activeHash,
    runId: activeRunId,
    className: activeClassParam,
  } = useParams<{ hashContent?: string; runId?: string; className?: string }>();
  const navigate = useNavigate();
  const groups = useAgentGroups();
  const [page, setPage] = useState(0);

  const className = decodeURIComponent(activeClassParam ?? "");

  const filtered = useMemo(() => {
    if (!groups.data) return [] as ClassGroup[];
    const q = search.trim().toLowerCase();
    const grouped = groupByClass(groups.data);
    if (!q) return grouped;
    return grouped
      .map((entry) => ({
        ...entry,
        instances: entry.instances.filter((instance) => {
          const hay = [
            entry.class_name,
            instance.root_agent_path ?? "",
            instance.hash_content,
            ...instance.run_ids,
          ]
            .join(" ")
            .toLowerCase();
          return hay.includes(q);
        }),
      }))
      .filter((entry) => entry.instances.length > 0);
  }, [groups.data, search]);

  const paged = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  const rows: GroupTreeRow[] = useMemo(
    () => paged.map((group) => buildClassRow(group, className, activeHash ?? null, activeRunId ?? null)),
    [paged, className, activeHash, activeRunId],
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
    if (row.id.startsWith("class::")) {
      const decodedClassName = decodeURIComponent(row.id.slice("class::".length));
      navigate(`/agents/_class_/${encodeURIComponent(decodedClassName)}`);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 overflow-auto">
        {groups.isLoading ? (
          <div className="p-3 text-xs text-muted">loading agents…</div>
        ) : (
          <GroupTreeSection
            label="Classes"
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

type ClassGroup = {
  class_name: string;
  instances: AgentGroupSummary[];
};

function buildClassRow(
  group: ClassGroup,
  activeClass: string,
  activeHash: string | null,
  activeRunId: string | null,
): GroupTreeRow {
  const running = group.instances.reduce((sum, instance) => sum + instance.running, 0);
  const errors = group.instances.reduce((sum, instance) => sum + instance.errors, 0);
  const state = running > 0 ? "running" : errors > 0 ? "error" : "ended";
  return {
    id: `class::${encodeURIComponent(group.class_name)}`,
    label: group.class_name,
    meta: `${group.instances.length} instance${group.instances.length === 1 ? "" : "s"}`,
    colorIdentity: group.class_name,
    state,
    active: activeClass === group.class_name,
    count: group.instances.length,
    children: group.instances.map((instance) => buildInstanceRow(instance, activeHash, activeRunId)),
  };
}

function buildInstanceRow(
  g: AgentGroupSummary,
  activeHash: string | null,
  activeRunId: string | null,
): GroupTreeRow {
  const isActive = activeHash === g.hash_content && !activeRunId;
  const meta = g.is_trainer
    ? `Trainer · ${formatRelativeTime(g.last_seen)}`
    : formatRelativeTime(g.last_seen);
  const sparkline = g.latencies.slice(-12);
  const state = g.running > 0 ? "running" : g.errors > 0 ? "error" : "ended";
  const children: GroupTreeRow[] = g.run_ids.slice().reverse().map((runId) => ({
    id: `run::${g.hash_content}::${runId}`,
    label: <span className="font-mono text-[11px]">{truncateMiddle(runId, 14)}</span>,
    meta: <span>invocation</span>,
    colorIdentity: g.hash_content,
    state: "ended",
    active: activeHash === g.hash_content && activeRunId === runId,
  }));
  return {
    id: `instance::${g.hash_content}`,
    label: <span className="font-mono text-[11px]">{truncateMiddle(g.hash_content, 12)}</span>,
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

function groupByClass(groups: AgentGroupSummary[]): ClassGroup[] {
  const byClass = new Map<string, AgentGroupSummary[]>();
  for (const group of groups) {
    const className = group.class_name ?? "Agent";
    const existing = byClass.get(className);
    if (existing) {
      existing.push(group);
    } else {
      byClass.set(className, [group]);
    }
  }
  return [...byClass.entries()]
    .map(([class_name, instances]) => ({
      class_name,
      instances: instances.slice().sort((a, b) => b.last_seen - a.last_seen),
    }))
    .sort(
      (a, b) =>
        b.instances.length - a.instances.length || a.class_name.localeCompare(b.class_name),
    );
}
