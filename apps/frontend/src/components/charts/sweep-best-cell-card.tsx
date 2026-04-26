import { EmptyState } from "@/components/ui/empty-state";
import { SweepSnapshot } from "@/lib/types";

export function SweepBestCellCard({ data }: { data: unknown }) {
  const parsed = SweepSnapshot.safeParse(data);
  if (!parsed.success || parsed.data.cells.length === 0) {
    return <EmptyState title="no best cell yet" description="waiting for sweep to complete" />;
  }
  const { cells, best_cell_index } = parsed.data;
  const best =
    best_cell_index !== null ? cells.find((c) => c.cell_index === best_cell_index) : null;

  if (!best) {
    return <EmptyState title="best cell unknown" description="scores not yet available" />;
  }

  const entries = Object.entries(best.parameters);

  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[12px]">
      {entries.map(([k, v]) => (
        <>
          <dt key={`k-${k}`} className="font-medium text-muted">
            {k}
          </dt>
          <dd key={`v-${k}`} className="font-mono text-text">
            {String(v)}
          </dd>
        </>
      ))}
      <dt className="font-medium text-muted">score</dt>
      <dd className="font-mono text-text">{best.score !== null ? best.score.toFixed(4) : "—"}</dd>
    </dl>
  );
}
