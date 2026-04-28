import { Button, EmptyState, type RunRow, RunTable } from "@/components/ui";
import { useChildren } from "@/hooks/use-children";
import { defaultColumns as defaultDescriptor } from "@/lib/invocation-columns/default";
import { autoResearcherColumns } from "@/lib/invocation-columns/auto_researcher";
import { beamColumns } from "@/lib/invocation-columns/beam";
import { debateColumns } from "@/lib/invocation-columns/debate";
import { evogradientColumns } from "@/lib/invocation-columns/evogradient";
import { oproColumns } from "@/lib/invocation-columns/opro";
import { selfrefineColumns } from "@/lib/invocation-columns/selfrefine";
import { sweepColumns } from "@/lib/invocation-columns/sweep";
import { talkerReasonerColumns } from "@/lib/invocation-columns/talker_reasoner";
import type { AlgorithmColumns } from "@/lib/invocation-columns/types";
import { trainerColumns } from "@/lib/invocation-columns/trainer";
import { verifierColumns } from "@/lib/invocation-columns/verifier";
import { RunSummary as RunSummarySchema, type RunSummary } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const DESCRIPTORS: Record<string, AlgorithmColumns> = {
  Sweep: sweepColumns,
  Beam: beamColumns,
  BeamSearch: beamColumns,
  Debate: debateColumns,
  EvoGradient: evogradientColumns,
  Trainer: trainerColumns,
  OPRO: oproColumns,
  SelfRefine: selfrefineColumns,
  AutoResearcher: autoResearcherColumns,
  TalkerReasoner: talkerReasonerColumns,
  Verifier: verifierColumns,
};

export interface InvocationsTabProps {
  runId: string;
  algorithmClass?: string | null;
  defaultGroupBy?: string;
}

export function resolveAlgorithmColumns(
  algorithmClass: string | null | undefined,
): AlgorithmColumns {
  if (!algorithmClass) return defaultDescriptor;
  return DESCRIPTORS[algorithmClass] ?? defaultDescriptor;
}

export function InvocationsTab({ runId, algorithmClass, defaultGroupBy }: InvocationsTabProps) {
  const navigate = useNavigate();
  const children = useChildren(runId);
  const [selected, setSelected] = useState<string[]>([]);
  const [tableVersion, setTableVersion] = useState(0);
  const summary = useQuery({
    queryKey: ["run", "summary", runId] as const,
    queryFn: async () => {
      const response = await fetch(`/runs/${runId}/summary`, {
        headers: { accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText} <- /runs/${runId}/summary`);
      }
      return RunSummarySchema.parse(await response.json());
    },
    enabled: runId.length > 0 && !algorithmClass,
    staleTime: 30_000,
  });

  const resolvedClass = algorithmClass ?? summary.data?.algorithm_class ?? null;
  const descriptor = resolveAlgorithmColumns(resolvedClass);
  const rows = useMemo(() => {
    const parent = summary.data ?? null;
    const items = children.data ?? [];
    return items.map((child, index) => {
      const previous = index > 0 ? items[index - 1] ?? null : null;
      return descriptor.rowMapper(child, parent, index, previous);
    });
  }, [children.data, descriptor, summary.data]);

  const groupByKey = defaultGroupBy ?? descriptor.defaultGroupBy ?? "none";
  const groupBy = useMemo(() => {
    if (groupByKey === "none") return undefined;
    return (row: RunRow) => {
      const label = labelFromField(row, groupByKey);
      return { key: `${groupByKey}:${label}`, label: `${groupByKey} ${label}` };
    };
  }, [groupByKey]);

  if (children.isLoading || (!algorithmClass && summary.isLoading)) {
    return <div className="p-4 text-xs text-muted">loading invocations...</div>;
  }

  if (children.error || (!algorithmClass && summary.error)) {
    return (
      <EmptyState
        title="invocations unavailable"
        description="the dashboard could not load invocation rows for this run"
      />
    );
  }

  const storageClass = descriptor.algorithmClass.toLowerCase();
  const parentSummary: RunSummary | null = summary.data ?? null;

  return (
    <div className="h-full overflow-auto p-4">
      {selected.length >= 2 ? (
        <div className="sticky bottom-0 z-10 mb-3 flex items-center gap-2 border border-border bg-bg-1 px-3 py-2 text-[12px] text-text">
          <span className="font-mono">{selected.length} selected</span>
          <Button
            size="sm"
            variant="primary"
            onClick={() =>
              navigate(`/experiments?runs=${selected.map(encodeURIComponent).join(",")}`)
            }
          >
            Compare
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setSelected([]);
              setTableVersion((current) => current + 1);
            }}
          >
            Clear
          </Button>
        </div>
      ) : null}
      <RunTable
        key={tableVersion}
        rows={rows}
        columns={descriptor.columns}
        storageKey={`invocations:${storageClass}:${runId}`}
        rowHref={(row) => rowHref(row, parentSummary)}
        {...(groupBy ? { groupBy } : {})}
        selectable
        onSelectionChange={setSelected}
        emptyTitle="no invocations yet"
        emptyDescription="child invocations will appear here once the algorithm emits work units"
        pageSize={50}
      />
    </div>
  );
}

function rowHref(row: RunRow, parent: RunSummary | null): string | null {
  if (!row.identity || row.id.length === 0) return null;
  if (parent?.algorithm_class === "OPRO") return `/opro/${encodeURIComponent(row.id)}`;
  if (parent?.algorithm_class === "Trainer") return `/training/${encodeURIComponent(row.id)}`;
  return `/agents/${encodeURIComponent(row.identity)}/runs/${encodeURIComponent(row.id)}`;
}

function labelFromField(row: RunRow, key: string): string {
  if (key === "state") return row.state;
  const field = row.fields[key];
  if (!field) return "—";
  if (field.kind === "text") return field.value;
  if (field.kind === "num") return field.value == null ? "—" : String(Math.round(field.value));
  if (field.kind === "pill") return field.value;
  if (field.kind === "param") {
    if (typeof field.value === "string") return field.value;
    try {
      return JSON.stringify(field.value) ?? "—";
    } catch {
      return "—";
    }
  }
  if (field.kind === "score") return field.value == null ? "—" : field.value.toFixed(3);
  return "—";
}
