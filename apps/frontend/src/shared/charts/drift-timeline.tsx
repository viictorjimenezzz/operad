import { useState } from "react";
import { DriftEntry } from "@/lib/types";
import { EmptyState } from "@/shared/ui/empty-state";
import { PromptDriftDiff } from "./prompt-drift-diff";
import { z } from "zod";

const Schema = z.array(DriftEntry);

export function DriftTimeline({ data }: { data: unknown }) {
  const parsed = Schema.safeParse(data);
  const [selectedEpoch, setSelectedEpoch] = useState<number | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  if (!parsed.success || parsed.data.length === 0) {
    return <EmptyState title="no drift events" description="PromptDrift callback hasn't fired" />;
  }

  const entries = [...parsed.data].sort((a, b) => a.epoch - b.epoch);
  const lastEntry = entries[entries.length - 1]!;
  const epoch = selectedEpoch ?? lastEntry.epoch;
  const entry = entries.find((e) => e.epoch === epoch) ?? lastEntry;
  const activePath =
    selectedPath && entry.changes.some((c) => c.path === selectedPath)
      ? selectedPath
      : (entry.selected_path || entry.changes[0]?.path || null);
  const activeChange = entry.changes.find((c) => c.path === activePath) ?? entry.changes[0];

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
        {entry.changes.length > 1 && (
          <>
            <span className="text-muted">param</span>
            <select
              className="rounded border border-border bg-bg-2 px-2 py-0.5 text-xs"
              value={activePath ?? ""}
              onChange={(e) => setSelectedPath(e.target.value)}
            >
              {entry.changes.map((c) => (
                <option key={c.path} value={c.path}>
                  {c.path}
                </option>
              ))}
            </select>
          </>
        )}
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
      </div>
      <PromptDriftDiff
        before={activeChange?.before_text ?? entry.before_text}
        after={activeChange?.after_text ?? entry.after_text}
        {...(activePath ? { selectedPath: activePath } : {})}
        critique={entry.critique}
      />
    </div>
  );
}
