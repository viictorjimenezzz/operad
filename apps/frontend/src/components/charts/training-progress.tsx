import { EmptyState } from "@/components/ui/empty-state";
import { ProgressSnapshot } from "@/lib/types";
import { formatDurationMs } from "@/lib/utils";

export function TrainingProgress({ data }: { data: unknown }) {
  const parsed = ProgressSnapshot.safeParse(data);
  if (!parsed.success) return <EmptyState title="no training in progress" />;
  const p = parsed.data;
  const epochPct = p.epochs_total ? Math.min(100, (p.epoch / p.epochs_total) * 100) : null;
  const batchPct = p.batches_total ? Math.min(100, (p.batch / p.batches_total) * 100) : null;

  return (
    <div className="flex flex-col gap-3 text-xs">
      <Row
        label="epoch"
        value={p.epochs_total ? `${p.epoch} / ${p.epochs_total}` : `${p.epoch}`}
        pct={epochPct}
      />
      <Row
        label="batch"
        value={p.batches_total ? `${p.batch} / ${p.batches_total}` : `${p.batch}`}
        pct={batchPct}
      />
      <div className="grid grid-cols-3 gap-3 border-t border-border pt-3 text-muted">
        <Stat label="elapsed" value={formatDurationMs(p.elapsed_s * 1000)} />
        <Stat label="rate" value={`${p.rate_batches_per_s.toFixed(2)} b/s`} />
        <Stat label="eta" value={p.eta_s != null ? formatDurationMs(p.eta_s * 1000) : "—"} />
      </div>
      {p.finished && (
        <div className="rounded-md border border-ok bg-ok-dim/40 px-2 py-1 text-center text-[#aaf0be]">
          finished
        </div>
      )}
    </div>
  );
}

function Row({ label, value, pct }: { label: string; value: string; pct: number | null }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</span>
        <span className="font-mono tabular-nums">{value}</span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-bg-3">
        <div
          className="h-full bg-accent transition-all"
          style={{ width: pct == null ? "0%" : `${pct}%` }}
        />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</span>
      <span className="font-mono tabular-nums text-text">{value}</span>
    </div>
  );
}
