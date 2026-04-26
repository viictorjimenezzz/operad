import type { RunSummary } from "@/lib/types";
import type { MouseEvent as ReactMouseEvent } from "react";
import { RunRow } from "./run-row";

interface RunGroupSectionProps {
  label: string;
  runs: RunSummary[];
  selectedIds: Set<string>;
  onSelect: (runId: string, e: ReactMouseEvent) => void;
  activeRunId?: string | null;
}

export function RunGroupSection({
  label,
  runs,
  selectedIds,
  onSelect,
  activeRunId,
}: RunGroupSectionProps) {
  return (
    <details open className="group">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 border-b border-border px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-muted hover:text-text">
        <span className="flex-1">{label === "__agents__" ? "agents" : label}</span>
        <span className="rounded-full bg-bg-3 px-2 py-0.5 text-[10px] tabular-nums text-muted-2">
          {runs.length}
        </span>
      </summary>
      <ul>
        {runs.map((run) => (
          <RunRow
            key={run.run_id}
            run={run}
            active={run.run_id === activeRunId}
            selected={selectedIds.has(run.run_id)}
            onSelect={(e) => onSelect(run.run_id, e)}
          />
        ))}
      </ul>
    </details>
  );
}
