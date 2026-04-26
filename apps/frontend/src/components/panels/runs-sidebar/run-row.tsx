import { Badge } from "@/components/ui/badge";
import { usePinnedRuns } from "@/hooks/use-pinned-runs";
import { getAlgorithmMetric } from "@/lib/algorithm-metrics";
import type { RunSummary } from "@/lib/types";
import { formatRelativeTime, truncateMiddle } from "@/lib/utils";
import { Star } from "lucide-react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { Link } from "react-router-dom";

function StatusDot({ state }: { state: RunSummary["state"] }) {
  const base = "inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full";
  if (state === "running")
    return <span className={`${base} animate-pulse bg-[--color-ok]`} aria-label="running" />;
  if (state === "error") return <span className={`${base} bg-[--color-err]`} aria-label="error" />;
  return <span className={`${base} bg-[--color-muted-2]`} aria-label="ended" />;
}

interface RunRowProps {
  run: RunSummary;
  active: boolean;
  checked: boolean;
  onCheck: (e: ReactMouseEvent) => void;
}

export function RunRow({ run, active, checked, onCheck }: RunRowProps) {
  const { pinned, toggle } = usePinnedRuns();
  const isPinned = pinned.includes(run.run_id);

  return (
    <li>
      <Link
        to={`/runs/${run.run_id}`}
        className={`flex items-center gap-1.5 border-b border-border/60 px-2 py-1.5 transition-colors hover:bg-bg-2 ${
          active ? "bg-bg-2" : ""
        }`}
      >
        <input
          type="checkbox"
          checked={checked}
          aria-label={`select run ${run.run_id}`}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onCheck(e);
          }}
          onChange={() => {}}
          className="h-3 w-3 flex-shrink-0 cursor-pointer accent-[--color-accent]"
        />
        <StatusDot state={run.state} />
        <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-text">
          {truncateMiddle(run.run_id, 12)}
        </span>
        {run.algorithm_class && (
          <Badge variant="algo" className="flex-shrink-0 text-[9px]">
            {run.algorithm_class}
          </Badge>
        )}
        <span className="flex-shrink-0 text-[10px] tabular-nums text-muted">
          {getAlgorithmMetric(run)}
        </span>
        <span className="flex-shrink-0 text-[9px] text-muted-2">
          {formatRelativeTime(run.started_at)}
        </span>
        <button
          type="button"
          aria-label={isPinned ? "unpin run" : "pin run"}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            toggle(run.run_id);
          }}
          className="flex-shrink-0 text-muted hover:text-text"
        >
          <Star size={11} className={isPinned ? "fill-[--color-warn] text-[--color-warn]" : ""} />
        </button>
      </Link>
    </li>
  );
}
