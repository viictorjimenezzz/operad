import { EmptyState } from "@/components/ui/empty-state";
import { type RunRow, RunTable, type RunTableColumn } from "@/components/ui/run-table";
import { RunSummary as RunSummarySchema, SweepSnapshot } from "@/lib/types";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

interface SweepCellsTabProps {
  data: unknown;
  dataChildren?: unknown;
  runId: string;
}

export function SweepCellsTab({ data, dataChildren, runId }: SweepCellsTabProps) {
  const parsed = SweepSnapshot.safeParse(data);
  if (!parsed.success) {
    return <EmptyState title="no sweep cells" description="waiting for sweep events" />;
  }
  const snap = parsed.data;
  const children = parseChildren(dataChildren);
  const rows = snap.cells.map((cell): RunRow => {
    const child = children[cell.cell_index];
    const href = child ? childHref(child) : null;
    return {
      id: `cell-${cell.cell_index}`,
      identity:
        child?.hash_content ??
        child?.root_agent_path ??
        child?.run_id ??
        `${runId}:${cell.cell_index}`,
      state: child?.state ?? "ended",
      startedAt: child?.started_at ?? null,
      endedAt: child ? child.started_at + child.duration_ms / 1000 : null,
      durationMs: child?.duration_ms ?? null,
      fields: {
        cell: { kind: "num", value: cell.cell_index, format: "int" },
        ...Object.fromEntries(
          snap.axes.map((axis) => [
            axis.name,
            { kind: "text" as const, value: String(cell.parameters[axis.name] ?? "-"), mono: true },
          ]),
        ),
        score: { kind: "num", value: cell.score, format: "score" },
        cost: { kind: "num", value: child?.cost?.cost_usd ?? null, format: "cost" },
        latency: { kind: "num", value: child?.duration_ms ?? null, format: "ms" },
        run: href
          ? { kind: "link", label: "open", to: href }
          : { kind: "text", value: "-", mono: true },
      },
    };
  });

  const columns: RunTableColumn[] = [
    { id: "state", label: "State", source: "_state", sortable: true, width: 86 },
    { id: "cell", label: "Cell #", source: "cell", sortable: true, width: 72 },
    ...snap.axes.map(
      (axis): RunTableColumn => ({
        id: axis.name,
        label: axis.name,
        source: axis.name,
        sortable: true,
        width: "1fr",
      }),
    ),
    { id: "score", label: "Score", source: "score", sortable: true, align: "right", width: 82 },
    { id: "cost", label: "Cost", source: "cost", sortable: true, align: "right", width: 80 },
    {
      id: "latency",
      label: "Latency",
      source: "latency",
      sortable: true,
      align: "right",
      width: 88,
    },
    { id: "run", label: "Run", source: "run", width: 64 },
  ];

  return (
    <RunTable
      rows={rows}
      columns={columns}
      storageKey={`sweep-cells:${runId}`}
      rowHref={(row) => {
        const link = row.fields.run;
        return link?.kind === "link" ? link.to : null;
      }}
      emptyTitle="no sweep cells"
      emptyDescription="cell events have not arrived for this sweep"
    />
  );
}

function parseChildren(data: unknown): ChildRunSummary[] {
  const parsed = z.array(ChildRunSummary).safeParse(data);
  return parsed.success
    ? [...parsed.data].sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0))
    : [];
}

function childHref(child: ChildRunSummary): string {
  const identity = child.hash_content ?? child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}
