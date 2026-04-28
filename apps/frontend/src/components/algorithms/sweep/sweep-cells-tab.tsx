import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { type RunRow, RunTable, type RunTableColumn } from "@/components/ui/run-table";
import { RunSummary as RunSummarySchema, SweepSnapshot } from "@/lib/types";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
  langfuse_url: z.string().nullable().optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

interface SweepCellsTabProps {
  data: unknown;
  dataChildren?: unknown;
  runId: string;
}

export function SweepCellsTab({ data, dataChildren, runId }: SweepCellsTabProps) {
  const navigate = useNavigate();
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [tableVersion, setTableVersion] = useState(0);
  const parsed = SweepSnapshot.safeParse(data);
  if (!parsed.success) {
    return <EmptyState title="no sweep cells" description="waiting for sweep events" />;
  }
  const snap = parsed.data;
  const children = parseChildren(dataChildren);
  const previousByCell = buildPreviousByCell(snap.cells);
  const [scoreMin, scoreMax] = scoreRange(snap);
  const rows = snap.cells.map((cell): RunRow => {
    const child = children[cell.cell_index];
    const href = child ? childHref(child) : null;
    const previousCell = previousByCell.get(cell.cell_index);
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
            {
              kind: "param" as const,
              value: cell.parameters[axis.name] ?? null,
              previous: previousCell?.parameters[axis.name],
              format: axis.values.every((value) => typeof value === "number") ? "number" : "auto",
            },
          ]),
        ),
        score: { kind: "score", value: cell.score, min: scoreMin, max: scoreMax },
        cost: { kind: "num", value: child?.cost?.cost_usd ?? null, format: "cost" },
        latency: { kind: "num", value: child?.duration_ms ?? null, format: "ms" },
        run: href
          ? { kind: "link", label: "open", to: href }
          : { kind: "text", value: "-", mono: true },
        langfuse: child?.langfuse_url
          ? { kind: "link", label: "open", to: child.langfuse_url }
          : { kind: "text", value: "—" },
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
    { id: "langfuse", label: "Langfuse", source: "langfuse", width: 92 },
    { id: "run", label: "Run", source: "run", width: 64 },
  ];
  const selected = useMemo(() => selectedRunIds(selectedRows, rows), [rows, selectedRows]);

  return (
    <div className="space-y-3">
      {selected.length >= 2 ? (
        <div className="sticky bottom-0 z-10 flex items-center gap-2 border border-border bg-bg-1 px-3 py-2 text-[12px] text-text">
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
              setSelectedRows([]);
              setTableVersion((value) => value + 1);
            }}
          >
            Clear
          </Button>
        </div>
      ) : null}
      <RunTable
        key={tableVersion}
        rows={rows}
        columns={columns}
        storageKey={`sweep-cells:${runId}`}
        rowHref={(row) => {
          const link = row.fields.run;
          return link?.kind === "link" ? link.to : null;
        }}
        selectable
        onSelectionChange={setSelectedRows}
        emptyTitle="no sweep cells"
        emptyDescription="cell events have not arrived for this sweep"
      />
    </div>
  );
}

function selectedRunIds(selected: string[], rows: RunRow[]): string[] {
  const byRowId = new Map(rows.map((row) => [row.id, row]));
  return selected
    .map((id) => {
      const row = byRowId.get(id);
      const link = row?.fields.run;
      if (link?.kind !== "link") return null;
      const encoded = link.to.split("/").at(-1);
      return encoded ? decodeURIComponent(encoded) : null;
    })
    .filter((runId): runId is string => runId != null && runId.length > 0);
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

function buildPreviousByCell(cells: SweepSnapshot["cells"]): Map<number, SweepSnapshot["cells"][number]> {
  const out = new Map<number, SweepSnapshot["cells"][number]>();
  const sorted = [...cells].sort((a, b) => a.cell_index - b.cell_index);
  for (let index = 1; index < sorted.length; index += 1) {
    const current = sorted[index];
    const previous = sorted[index - 1];
    if (current && previous) out.set(current.cell_index, previous);
  }
  return out;
}

function scoreRange(snap: SweepSnapshot): [number, number] {
  if (snap.score_range) return snap.score_range;
  const values = snap.cells
    .map((cell) => cell.score)
    .filter((value): value is number => value != null && Number.isFinite(value));
  if (values.length === 0) return [0, 1];
  let min = values[0] ?? 0;
  let max = values[0] ?? 0;
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return [min, max];
}
