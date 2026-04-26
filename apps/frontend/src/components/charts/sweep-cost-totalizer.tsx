import { EmptyState } from "@/components/ui/empty-state";
import { SweepSnapshot } from "@/lib/types";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function SweepCostTotalizer({ data }: { data: unknown }) {
  const parsed = SweepSnapshot.safeParse(data);
  if (!parsed.success) {
    return <EmptyState title="no sweep data" description="waiting for cells to complete" />;
  }
  const { cells, total_cells, finished } = parsed.data;

  const completed = cells.length;
  const scoredPoints = cells
    .filter((c) => c.score !== null)
    .map((c) => ({ x: c.cell_index, y: c.score as number }));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-6 text-[12px]">
        <span className="text-muted">
          cells completed:{" "}
          <span className="font-mono text-text">
            {completed}/{total_cells}
          </span>
        </span>
        <span className="text-muted">
          status:{" "}
          <span className={`font-mono ${finished ? "text-ok" : "text-accent"}`}>
            {finished ? "finished" : "running"}
          </span>
        </span>
      </div>
      {scoredPoints.length > 0 ? (
        <ResponsiveContainer width="100%" height={180}>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis
              dataKey="x"
              name="cell"
              type="number"
              tick={{ fontSize: 11 }}
              label={{ value: "cell index", position: "insideBottom", offset: -4, fontSize: 11 }}
            />
            <YAxis dataKey="y" name="score" tick={{ fontSize: 11 }} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={scoredPoints} fill="rgba(70, 167, 255, 0.7)" />
          </ScatterChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-[11px] text-muted">no scored cells yet</p>
      )}
    </div>
  );
}
