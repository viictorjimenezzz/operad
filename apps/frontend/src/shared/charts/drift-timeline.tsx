import { useState } from "react";
import { DriftEntry } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
import { PromptDriftDiff } from "./prompt-drift-diff";
import { z } from "zod";

const Schema = z.array(DriftEntry);

export function DriftTimeline({ data }: { data: unknown }) {
  const parsed = Schema.safeParse(data);
  const [selectedEpoch, setSelectedEpoch] = useState<number | null>(null);

  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no drift events" description="PromptDrift callback hasn't fired" />;
  }

  const entries = [...parsed.data].sort((a, b) => a.epoch - b.epoch);
  const epoch = selectedEpoch ?? entries[entries.length - 1].epoch;
  const entry = entries.find((e) => e.epoch === epoch) ?? entries[entries.length - 1];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted">epoch</span>
        <select
          className="rounded border border-border bg-bg-2 px-2 py-0.5 text-xs"
          value={epoch}
          onChange={(e) => setSelectedEpoch(Number(e.target.value))}
        >
          {entries.map((e) => (
            <option key={e.epoch} value={e.epoch}>
              {e.epoch}
            </option>
          ))}
        </select>
        {entry.changed_params.length > 0 && (
          <div className="flex flex-wrap gap-1">
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
        <span className="ml-auto text-[10px] text-muted">
          prompt text not yet available — showing parameter hashes
        </span>
      </div>
      <PromptDriftDiff before={entry.hash_before} after={entry.hash_after} />
    </div>
  );
}
