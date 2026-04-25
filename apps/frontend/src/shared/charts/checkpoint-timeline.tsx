import { CheckpointEntry } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
import { z } from "zod";

const Schema = z.array(CheckpointEntry);

function fmt(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(4);
}

export function CheckpointTimeline({ data }: { data: unknown }) {
  const parsed = Schema.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no checkpoints yet" description="Trainer epoch_end events haven't fired" />;
  }

  const entries = [...parsed.data].sort((a, b) => a.epoch - b.epoch);

  return (
    <ol className="relative flex flex-col gap-0 pl-6 text-xs before:absolute before:left-2 before:top-0 before:h-full before:w-px before:bg-border">
      {entries.map((entry) => (
        <li key={entry.epoch} className="relative pb-4">
          <div className="absolute -left-4 top-1 h-2 w-2 rounded-full border border-border bg-bg-3" />
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">
              epoch {entry.epoch}
            </span>
            {entry.is_best && (
              <span className="rounded border border-accent px-1.5 py-0.5 text-[10px] text-accent">
                best
              </span>
            )}
          </div>
          <div className="mt-0.5 flex gap-3 font-mono text-[11px]">
            <span>
              <span className="text-muted">train </span>
              {fmt(entry.train_loss)}
            </span>
            {entry.val_loss != null && (
              <span>
                <span className="text-muted">val </span>
                {fmt(entry.val_loss)}
              </span>
            )}
            <span>
              <span className="text-muted">score </span>
              {fmt(entry.score)}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}
