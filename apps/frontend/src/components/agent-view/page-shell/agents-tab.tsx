import { Button, EmptyState, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";
import { type ChildRunSummary, useChildren } from "@/hooks/use-children";
import { SweepSnapshot } from "@/lib/types";
import { formatDurationMs, truncateMiddle } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

interface AgentsTabProps {
  runId: string;
  groupBy?: "hash" | "none";
  extraColumns?: string[];
  emptyTitle?: string;
  emptyDescription?: string;
}

const defaultColumns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
  { id: "agent", label: "Agent class", source: "agent", sortable: true, width: "1fr" },
  { id: "hash", label: "hash_content", source: "hash", sortable: true, width: 150 },
  {
    id: "invocations",
    label: "# inv",
    source: "invocations",
    sortable: true,
    align: "right",
    width: 70,
  },
  { id: "started", label: "Started", source: "_started", sortable: true, width: 110 },
  { id: "last", label: "Last seen", source: "_ended", sortable: true, width: 110 },
  {
    id: "latency",
    label: "Latency p50",
    source: "latency",
    sortable: true,
    align: "right",
    width: 92,
  },
  { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 78 },
];

const extraColumnSpecs: Record<string, RunTableColumn> = {
  score: {
    id: "score",
    label: "Score",
    source: "score",
    sortable: true,
    align: "right",
    width: 78,
  },
  axisValues: { id: "axisValues", label: "Axis values", source: "axisValues", width: "1fr" },
  attempt_index: {
    id: "attempt_index",
    label: "Attempt",
    source: "attempt_index",
    sortable: true,
    align: "right",
    width: 82,
  },
  gen: { id: "gen", label: "Gen", source: "gen", sortable: true, align: "right", width: 64 },
  individual_id: {
    id: "individual_id",
    label: "Individual",
    source: "individual_id",
    sortable: true,
    width: 98,
  },
};

export function AgentsTab({
  runId,
  groupBy = "hash",
  extraColumns = [],
  emptyTitle = "no agent invocations yet",
  emptyDescription = "this algorithm has not spawned synthetic children yet; the first algo_emit lands as soon as the algorithm enters its main loop",
}: AgentsTabProps) {
  const children = useChildren(runId);
  const sweep = useQuery({
    queryKey: ["run", "sweep", runId] as const,
    queryFn: async () => {
      const response = await fetch(`/runs/${runId}/sweep.json`);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText} <- /runs/${runId}/sweep.json`);
      }
      return SweepSnapshot.parse(await response.json());
    },
    enabled:
      runId.length > 0 && (extraColumns.includes("axisValues") || extraColumns.includes("score")),
    staleTime: 30_000,
  });
  const [grouped, setGrouped] = useState(groupBy !== "none");

  useEffect(() => {
    setGrouped(groupBy !== "none");
  }, [groupBy]);

  const columns = useMemo(() => buildColumns(extraColumns), [extraColumns]);
  const rows = useMemo(
    () =>
      (children.data ?? []).map((child, index) =>
        childToRow(child, extraColumns, index, sweep.data),
      ),
    [children.data, extraColumns, sweep.data],
  );
  const groupLabels = useMemo(() => buildGroupLabels(rows), [rows]);

  if (children.isLoading) {
    return <div className="p-4 text-xs text-muted">loading child agents...</div>;
  }
  if (children.error) {
    return (
      <EmptyState
        title="child agents unavailable"
        description="the dashboard could not load synthetic child runs for this algorithm"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[12px] text-muted">
          {rows.length === 1 ? "1 child run" : `${rows.length} child runs`}
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setGrouped((current) => !current)}
          aria-pressed={grouped}
        >
          {grouped ? "ungroup" : "group"}
        </Button>
      </div>
      <RunTable
        rows={rows}
        columns={columns}
        storageKey={`agents-tab:${runId}`}
        rowHref={(row) => childHref(row)}
        {...(grouped ? { groupBy: (row) => groupByHash(row, groupLabels) } : {})}
        emptyTitle={emptyTitle}
        emptyDescription={emptyDescription}
        pageSize={50}
      />
    </div>
  );
}

function buildColumns(extraColumns: string[]): RunTableColumn[] {
  const extras = extraColumns.flatMap((key) => {
    const spec = extraColumnSpecs[key];
    return spec ? [spec] : [];
  });
  return [...defaultColumns, ...extras];
}

function childToRow(
  child: ChildRunSummary,
  extraColumns: string[],
  index: number,
  sweep: SweepSnapshot | undefined,
): RunRow {
  const hash = childHash(child);
  const className = child.algorithm_class ?? child.root_agent_path?.split(".").at(-1) ?? "Agent";
  const totalTokens = child.prompt_tokens + child.completion_tokens;
  const sweepCell = sweep?.cells[index] ?? null;
  const fields: RunRow["fields"] = {
    agent: { kind: "text", value: className, mono: true },
    hash: { kind: "hash", value: hash },
    group: { kind: "text", value: hash, mono: true },
    groupLabel: { kind: "text", value: className },
    invocations: { kind: "num", value: child.event_counts.end ?? child.event_total, format: "int" },
    latency: { kind: "num", value: child.duration_ms, format: "ms" },
    tokens: { kind: "num", value: totalTokens, format: "tokens" },
    cost: { kind: "num", value: child.cost?.cost_usd ?? null, format: "cost" },
  };

  for (const key of extraColumns) {
    const value = extraField(child, key, sweepCell);
    if (value !== null) fields[key] = value;
  }

  return {
    id: child.run_id,
    identity: hash,
    state: child.state,
    startedAt: child.started_at,
    endedAt: child.last_event_at,
    durationMs: child.duration_ms,
    fields,
  };
}

function buildGroupLabels(rows: RunRow[]): Map<string, string> {
  const groups = new Map<string, RunRow[]>();
  for (const row of rows) {
    const existing = groups.get(row.identity);
    if (existing) existing.push(row);
    else groups.set(row.identity, [row]);
  }
  return new Map(
    [...groups.entries()].map(([hash, groupRows]) => {
      const agent = textField(groupRows[0]?.fields.groupLabel) ?? "Agent";
      const latency = median(
        groupRows
          .map((row) => (row.fields.latency?.kind === "num" ? row.fields.latency.value : null))
          .filter((value): value is number => value !== null),
      );
      const latencyLabel = latency === null ? "p50 -" : `p50 ${formatDurationMs(latency)}`;
      return [hash, `${agent} ${truncateMiddle(hash, 14)} ${latencyLabel}`];
    }),
  );
}

function groupByHash(row: RunRow, labels: Map<string, string>): { key: string; label: string } {
  const field = row.fields.group;
  const value = field?.kind === "text" ? field.value : row.identity;
  return { key: value, label: labels.get(value) ?? truncateMiddle(value, 24) };
}

function childHref(row: RunRow): string {
  return `/agents/${encodeURIComponent(row.identity)}/runs/${encodeURIComponent(row.id)}`;
}

function childHash(child: ChildRunSummary): string {
  return (
    child.hash_content ??
    stringAt(child.metadata, "hash_content") ??
    stringAt(child.parent_run_metadata, "hash_content") ??
    child.root_agent_path ??
    child.run_id
  );
}

function extraField(
  child: ChildRunSummary,
  key: string,
  sweepCell: SweepSnapshot["cells"][number] | null,
): RunRow["fields"][string] | null {
  if (key === "score") {
    const score = numberAt(child.metrics, "score") ?? child.algorithm_terminal_score ?? sweepCell?.score;
    return { kind: "num", value: score ?? null, format: "score" };
  }
  if (key === "axisValues") {
    const values =
      valueAt(child.metadata, "algorithm_axis_values") ??
      valueAt(child.algorithm_metadata, "algorithm_axis_values") ??
      valueAt(child.parent_run_metadata, "algorithm_axis_values") ??
      valueAt(child.metadata, "axis_values") ??
      valueAt(child, "axis_values") ??
      sweepCell?.parameters;
    return values == null ? null : { kind: "text", value: shortValue(values), mono: true };
  }
  if (key === "attempt_index") {
    return { kind: "num", value: numberFromMetadata(child, "attempt_index"), format: "int" };
  }
  if (key === "gen") {
    return {
      kind: "num",
      value: numberFromMetadata(child, "gen") ?? numberFromMetadata(child, "gen_index"),
      format: "int",
    };
  }
  if (key === "individual_id") {
    const value = stringFromMetadata(child, "individual_id");
    return value == null ? null : { kind: "text", value, mono: true };
  }
  return null;
}

function numberFromMetadata(child: ChildRunSummary, key: string): number | null {
  return (
    numberAt(child.algorithm_metadata, key) ??
    numberAt(child.parent_run_metadata, key) ??
    numberAt(child.metadata, key)
  );
}

function stringFromMetadata(child: ChildRunSummary, key: string): string | null {
  return (
    stringAt(child.algorithm_metadata, key) ??
    stringAt(child.parent_run_metadata, key) ??
    stringAt(child.metadata, key)
  );
}

function valueAt(source: unknown, key: string): unknown {
  return isRecord(source) ? source[key] : undefined;
}

function numberAt(source: unknown, key: string): number | null {
  const value = valueAt(source, key);
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringAt(source: unknown, key: string): string | null {
  const value = valueAt(source, key);
  return typeof value === "string" && value.length > 0 ? value : null;
}

function textField(value: RunRow["fields"][string] | undefined): string | null {
  return value?.kind === "text" ? value.value : null;
}

function shortValue(value: unknown): string {
  if (isRecord(value)) {
    return Object.entries(value)
      .map(([key, item]) => `${key}=${String(item)}`)
      .join(", ");
  }
  if (Array.isArray(value)) return value.map((item) => String(item)).join(", ");
  return String(value);
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const value = sorted[mid];
  if (value === undefined) return null;
  if (sorted.length % 2 === 1) return value;
  const prev = sorted[mid - 1] ?? value;
  return (prev + value) / 2;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
