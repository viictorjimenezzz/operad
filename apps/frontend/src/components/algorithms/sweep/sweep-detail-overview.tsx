import { SweepBestCellCard } from "@/components/charts/sweep-best-cell-card";
import { SweepCostTotalizer } from "@/components/charts/sweep-cost-totalizer";
import { EmptyState } from "@/components/ui/empty-state";
import { PanelCard } from "@/components/ui/panel-card";
import { PanelGrid, PanelGridItem } from "@/components/ui/panel-grid";
import { StatusDot } from "@/components/ui/status-dot";
import { RunSummary as RunSummarySchema, SweepSnapshot } from "@/lib/types";
import { formatCost, formatDurationMs, formatNumber } from "@/lib/utils";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

const ChildRunSummary = RunSummarySchema.passthrough().extend({
  hash_content: z.string().nullable().optional(),
});

type ChildRunSummary = z.infer<typeof ChildRunSummary>;

interface SweepDetailOverviewProps {
  data: unknown;
  dataSummary?: unknown;
  dataChildren?: unknown;
}

export function SweepDetailOverview({ data, dataSummary }: SweepDetailOverviewProps) {
  const parsed = SweepSnapshot.safeParse(data);
  const summary = RunSummarySchema.safeParse(dataSummary).success
    ? RunSummarySchema.parse(dataSummary)
    : null;

  if (!parsed.success) {
    return <EmptyState title="no sweep data" description="waiting for sweep events" />;
  }

  const snap = parsed.data;
  const scored = snap.cells.filter((cell) => cell.score != null);
  const best =
    snap.best_cell_index != null
      ? snap.cells.find((cell) => cell.cell_index === snap.best_cell_index)
      : null;
  const failed = snap.finished ? Math.max(0, snap.total_cells - snap.cells.length) : 0;
  const pending = snap.finished ? 0 : Math.max(0, snap.total_cells - snap.cells.length);

  return (
    <div className="flex flex-col gap-3">
      <PanelGrid cols={4} gap="sm">
        <Kpi label="axes" value={snap.axes.length.toString()} />
        <Kpi label="cells" value={`${snap.cells.length}/${snap.total_cells}`} />
        <Kpi label="ok" value={snap.cells.length.toString()} />
        <Kpi
          label={snap.finished ? "failed" : "pending"}
          value={(snap.finished ? failed : pending).toString()}
        />
        <Kpi
          label="best score"
          value={best?.score != null ? formatNumber(best.score) : scored.length ? "-" : "unscored"}
        />
        <Kpi label="cost" value={formatCost(summary?.cost?.cost_usd ?? null)} />
        <Kpi label="runtime" value={formatDurationMs(summary?.duration_ms ?? null)} />
        <Kpi label="events" value={formatNumber(summary?.event_total ?? 0)} />
      </PanelGrid>

      <PanelGrid cols={2}>
        <PanelCard title="best cell">
          <SweepBestCellCard data={snap} />
        </PanelCard>
        <PanelCard title="cell progress">
          <SweepCostTotalizer data={snap} />
        </PanelCard>
      </PanelGrid>
    </div>
  );
}

export function SweepCostTab({ data, dataChildren }: SweepDetailOverviewProps) {
  const parsed = SweepSnapshot.safeParse(data);
  const children = parseChildren(dataChildren);
  if (!parsed.success || parsed.data.cells.length === 0) {
    return <EmptyState title="no sweep cost data" description="waiting for sweep cells" />;
  }

  const snap = parsed.data;
  const costByCell = childCostByCell(children);
  const cumulative = buildCumulativeCost(snap, costByCell);
  const axisCosts = buildAxisCosts(snap, costByCell);
  const frontier = paretoFrontier(snap, costByCell);

  return (
    <PanelGrid cols={2}>
      <PanelGridItem colSpan={2}>
        <PanelCard title="cost vs best score" bodyMinHeight={220}>
          {cumulative.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={cumulative} margin={{ top: 8, right: 18, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="cost"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(value) => formatCost(Number(value))}
                />
                <YAxis dataKey="best" tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(value, name) =>
                    name === "cost" ? formatCost(Number(value)) : formatNumber(Number(value))
                  }
                  contentStyle={{
                    background: "var(--color-bg-2)",
                    border: "1px solid var(--color-border)",
                    fontSize: 11,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="best"
                  stroke="var(--color-accent)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "var(--color-accent)" }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="no scored cells" description="cost frontier needs cell scores" />
          )}
        </PanelCard>
      </PanelGridItem>
      <PanelCard title="cost by axis" bodyMinHeight={220}>
        {axisCosts.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={axisCosts} margin={{ top: 8, right: 18, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => formatCost(Number(value))} />
              <Tooltip
                formatter={(value) => formatCost(Number(value))}
                contentStyle={{
                  background: "var(--color-bg-2)",
                  border: "1px solid var(--color-border)",
                  fontSize: 11,
                }}
              />
              <Bar
                dataKey="cost"
                fill="var(--color-accent)"
                fillOpacity={0.78}
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState
            title="no cell costs"
            description="synthetic child runs have not reported cost"
          />
        )}
      </PanelCard>
      <PanelCard title="pareto frontier">
        {frontier.length > 0 ? (
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-border text-muted">
                <th className="px-2 py-1 text-left font-medium">cell</th>
                <th className="px-2 py-1 text-right font-medium">score</th>
                <th className="px-2 py-1 text-right font-medium">cost</th>
              </tr>
            </thead>
            <tbody>
              {frontier.map((row) => (
                <tr key={row.cell.cell_index} className="border-b border-border/70 last:border-b-0">
                  <td className="px-2 py-1 font-mono">#{row.cell.cell_index}</td>
                  <td className="px-2 py-1 text-right font-mono">
                    {row.cell.score != null ? row.cell.score.toFixed(3) : "-"}
                  </td>
                  <td className="px-2 py-1 text-right font-mono">{formatCost(row.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="no frontier yet" description="frontier needs scored cells" />
        )}
      </PanelCard>
    </PanelGrid>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <PanelCard surface="inset" bare>
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.08em] text-muted-2">{label}</div>
        <div className="flex items-center gap-2 font-mono text-[15px] text-text">
          {label === "ok" ? <StatusDot state="ended" size="xs" /> : null}
          {label === "failed" ? <StatusDot state="error" size="xs" /> : null}
          {value}
        </div>
      </div>
    </PanelCard>
  );
}

function parseChildren(data: unknown): ChildRunSummary[] {
  const parsed = z.array(ChildRunSummary).safeParse(data);
  return parsed.success
    ? [...parsed.data].sort((a, b) => (a.started_at ?? 0) - (b.started_at ?? 0))
    : [];
}

function childCostByCell(children: ChildRunSummary[]): Map<number, number> {
  const out = new Map<number, number>();
  children.forEach((child, index) => {
    out.set(index, child.cost?.cost_usd ?? 0);
  });
  return out;
}

function buildCumulativeCost(snap: SweepSnapshot, costByCell: Map<number, number>) {
  let cost = 0;
  let best: number | null = null;
  const rows: Array<{ cell: number; cost: number; best: number }> = [];
  for (const cell of [...snap.cells].sort((a, b) => a.cell_index - b.cell_index)) {
    cost += costByCell.get(cell.cell_index) ?? 0;
    if (cell.score == null) continue;
    best = best == null ? cell.score : Math.max(best, cell.score);
    rows.push({ cell: cell.cell_index, cost, best });
  }
  return rows;
}

function buildAxisCosts(snap: SweepSnapshot, costByCell: Map<number, number>) {
  const totals = new Map<string, number>();
  for (const cell of snap.cells) {
    const cost = costByCell.get(cell.cell_index) ?? 0;
    for (const axis of snap.axes) {
      const key = `${axis.name}=${String(cell.parameters[axis.name])}`;
      totals.set(key, (totals.get(key) ?? 0) + cost);
    }
  }
  return [...totals.entries()]
    .map(([label, cost]) => ({ label, cost }))
    .filter((row) => row.cost > 0)
    .sort((a, b) => b.cost - a.cost)
    .slice(0, 12);
}

function paretoFrontier(snap: SweepSnapshot, costByCell: Map<number, number>) {
  const rows = snap.cells
    .filter((cell) => cell.score != null)
    .map((cell) => ({ cell, cost: costByCell.get(cell.cell_index) ?? 0 }));
  return rows
    .filter(
      (row) =>
        !rows.some(
          (other) =>
            other.cell.cell_index !== row.cell.cell_index &&
            other.cost <= row.cost &&
            (other.cell.score ?? Number.NEGATIVE_INFINITY) >=
              (row.cell.score ?? Number.NEGATIVE_INFINITY) &&
            (other.cost < row.cost ||
              (other.cell.score ?? Number.NEGATIVE_INFINITY) >
                (row.cell.score ?? Number.NEGATIVE_INFINITY)),
        ),
    )
    .sort((a, b) => (b.cell.score ?? 0) - (a.cell.score ?? 0));
}
