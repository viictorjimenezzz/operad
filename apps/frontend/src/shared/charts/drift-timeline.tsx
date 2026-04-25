import { DriftEntry } from "@/lib/types";
import { truncateMiddle } from "@/lib/utils";
import { EmptyState } from "@/shared/ui/empty-state";
import { z } from "zod";

const Schema = z.array(DriftEntry);

export function DriftTimeline({ data }: { data: unknown }) {
  const parsed = Schema.safeParse(data);
  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no drift events" description="PromptDrift callback hasn't fired" />;
  }
  return (
    <ol className="flex flex-col gap-2 text-xs">
      {parsed.data.map((entry) => (
        <li key={entry.epoch} className="rounded-md border border-border bg-bg-2 px-3 py-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">
              epoch {entry.epoch}
            </span>
            <span className="font-mono text-muted">
              {truncateMiddle(entry.hash_before, 10)} → {truncateMiddle(entry.hash_after, 10)}
            </span>
          </div>
          {entry.changed_params.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {entry.changed_params.map((p) => (
                <span
                  key={p}
                  className="rounded border border-border bg-bg-3 px-1.5 py-0.5 font-mono text-[10px]"
                >
                  {p}
                </span>
              ))}
            </div>
          )}
          {entry.delta_count > 0 && (
            <div className="mt-1 text-[10px] text-warn">
              {entry.delta_count} param{entry.delta_count === 1 ? "" : "s"} changed
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
