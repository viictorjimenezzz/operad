import { Breadcrumb, EmptyState, type RunRow, RunTable, type RunTableColumn } from "@/components/ui";
import { useAgentClasses } from "@/hooks/use-runs";
import { useMemo } from "react";
import { useParams } from "react-router-dom";

const columns: RunTableColumn[] = [
  { id: "state", label: "State", source: "_state", sortable: true, width: 80 },
  { id: "hash", label: "Instance", source: "hash", sortable: true, width: "1fr" },
  { id: "runs", label: "Runs", source: "runs", align: "right", sortable: true, width: 80 },
  {
    id: "last",
    label: "Last seen",
    source: "_ended",
    sortable: true,
    defaultSort: "desc",
    width: 90,
  },
  { id: "running", label: "Running", source: "running", align: "right", sortable: true, width: 90 },
  { id: "errors", label: "Errors", source: "errors", align: "right", sortable: true, width: 80 },
  { id: "cost", label: "Cost", source: "cost", align: "right", sortable: true, width: 90 },
];

export function AgentsByClassPage() {
  const { className: classNameParam } = useParams<{ className: string }>();
  const className = decodeURIComponent(classNameParam ?? "");
  const classes = useAgentClasses();

  const selectedClass = useMemo(
    () => classes.data?.find((entry) => entry.class_name === className) ?? null,
    [classes.data, className],
  );
  const rows = useMemo(() => (selectedClass ? selectedClass.instances.map(instanceRow) : []), [selectedClass]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Breadcrumb items={[{ label: "Agents", to: "/agents" }, { label: className || "Class" }]} />
      <div className="flex-1 overflow-auto p-4">
        {classes.isLoading ? (
          <div className="text-xs text-muted">loading class instances...</div>
        ) : !className ? (
          <EmptyState
            title="class is missing"
            description="open this page from the class index to choose a valid class"
          />
        ) : !selectedClass ? (
          <EmptyState
            title="class not found"
            description="this class has no instances in the current dashboard dataset"
          />
        ) : (
          <RunTable
            rows={rows}
            columns={columns}
            storageKey={`agents-class-${className}`}
            rowHref={(row) => `/agents/${row.id}`}
            emptyTitle="no instances yet"
            emptyDescription="this class has no recorded instances yet"
          />
        )}
      </div>
    </div>
  );
}

function instanceRow(instance: {
  hash_content: string;
  count: number;
  running: number;
  errors: number;
  first_seen: number;
  last_seen: number;
  cost_usd: number;
}): RunRow {
  const state = instance.running > 0 ? "running" : instance.errors > 0 ? "error" : "ended";
  return {
    id: instance.hash_content,
    identity: instance.hash_content,
    state,
    startedAt: instance.first_seen,
    endedAt: instance.last_seen,
    durationMs: null,
    fields: {
      hash: { kind: "hash", value: instance.hash_content },
      runs: { kind: "num", value: instance.count, format: "int" },
      running: { kind: "num", value: instance.running, format: "int" },
      errors: { kind: "num", value: instance.errors, format: "int" },
      cost: { kind: "num", value: instance.cost_usd, format: "cost" },
    },
  };
}
