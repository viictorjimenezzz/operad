import { Breadcrumb, EmptyState } from "@/components/ui";
import { RunTable, type RunRow, type RunTableColumn } from "@/components/ui/run-table";
import { dashboardApi } from "@/lib/api/dashboard";
import type { RunSummary } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

const ARCHIVE_COLUMNS: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", width: 86, sortable: true },
  {
    id: "run",
    label: "Run id",
    source: "run_id",
    sortable: true,
    width: "1fr",
    defaultSort: "desc",
  },
  { id: "agent", label: "Agent", source: "agent", width: "1fr", sortable: true },
  { id: "started", label: "Started", source: "_started", width: 110, sortable: true },
  { id: "duration", label: "Duration", source: "_duration", width: 96, align: "right", sortable: true },
  { id: "tokens", label: "Tokens", source: "tokens", width: 80, align: "right", sortable: true },
  { id: "cost", label: "Cost", source: "cost", width: 80, align: "right", sortable: true },
  { id: "events", label: "Events", source: "events", width: 72, align: "right", sortable: true },
];

export function ArchivePage() {
  const archive = useQuery({
    queryKey: ["archive"] as const,
    queryFn: () => dashboardApi.archive({ limit: 200 }),
  });
  const rows: RunRow[] = (archive.data ?? []).map(toRow);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Archive" }]} />
      <div className="flex-1 overflow-auto p-4">
        {archive.isLoading ? (
          <div className="text-xs text-muted">loading archive…</div>
        ) : rows.length === 0 ? (
          <EmptyState
            title="archive is empty"
            description="completed runs land here automatically when persistence is enabled (operad-dashboard --data-dir ./.dashboard-data)"
          />
        ) : (
          <RunTable
            rows={rows}
            columns={ARCHIVE_COLUMNS}
            storageKey="archive"
            rowHref={(r) =>
              r.fields.hash_content && r.fields.hash_content.kind === "text"
                ? `/agents/${r.fields.hash_content.value}/runs/${r.id}`
                : `/algorithms/${r.id}`
            }
            emptyTitle="No archived runs"
            emptyDescription="Runs are archived when --data-dir is set."
          />
        )}
      </div>
    </div>
  );
}

function toRow(run: RunSummary): RunRow {
  // Prefer the user-visible agent class. Algorithm orchestrators expose
  // it via `algorithm_class`; agent invocations carry `root_agent_path`.
  // Falling back to a literal "Agent" hides the class and was a regression.
  const agent =
    run.algorithm_class ??
    run.algorithm_path?.split(".").at(-1) ??
    run.root_agent_path?.split(".").at(-1) ??
    "Agent";
  return {
    id: run.run_id,
    identity: run.hash_content ?? run.run_id,
    state: run.state === "running" ? "running" : run.state === "error" ? "error" : "ended",
    startedAt: run.started_at,
    endedAt: run.state === "running" ? null : run.last_event_at,
    durationMs: run.duration_ms,
    fields: {
      run_id: { kind: "text", value: run.run_id, mono: true },
      agent: { kind: "text", value: agent },
      tokens: {
        kind: "num",
        value: run.prompt_tokens + run.completion_tokens,
        format: "tokens",
      },
      cost: { kind: "num", value: run.cost?.cost_usd ?? null, format: "cost" },
      events: { kind: "num", value: run.event_total, format: "int" },
      hash_content: { kind: "text", value: run.hash_content ?? "" },
    },
  };
}
