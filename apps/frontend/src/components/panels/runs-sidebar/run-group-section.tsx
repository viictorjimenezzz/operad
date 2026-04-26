import type { RunSummary } from "@/lib/types";
import type { MouseEvent as ReactMouseEvent } from "react";
import { RunRow } from "./run-row";

interface RunGroupSectionProps {
  label: string;
  runs: RunSummary[];
  selectedIds: Set<string>;
  onCheck: (runId: string, e: ReactMouseEvent) => void;
  activeRunId?: string | undefined;
}

export function RunGroupSection({
  label,
  runs,
  selectedIds,
  onCheck,
  activeRunId,
}: RunGroupSectionProps) {
  return (
    <details open className="group">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 border-b border-border bg-bg-1 px-2 py-1 text-[0.68rem] uppercase tracking-[0.1em] text-muted hover:text-text">
        <span className="flex-1">{label === "__agents__" ? "agents" : label}</span>
        <span className="rounded-full bg-bg-3 px-1.5 py-0.5 text-[9px] tabular-nums text-muted-2">
          {runs.length}
        </span>
      </summary>
      <ul>
        {runs.map((run) => (
          <RunRow
            key={run.run_id}
            run={run}
            active={run.run_id === activeRunId}
            checked={selectedIds.has(run.run_id)}
            onCheck={(e) => onCheck(run.run_id, e)}
          />
        ))}
      </ul>
    </details>
  );
}
