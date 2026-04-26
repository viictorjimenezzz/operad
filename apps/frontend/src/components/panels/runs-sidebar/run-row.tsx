import { HashTag, Pill } from "@/components/ui";
import { getAlgorithmMetric } from "@/lib/algorithm-metrics";
import type { RunSummary } from "@/lib/types";
import { cn, formatRelativeTime, truncateMiddle } from "@/lib/utils";
import type { MouseEvent as ReactMouseEvent } from "react";
import { Link } from "react-router-dom";

interface RunRowProps {
  run: RunSummary;
  active: boolean;
  selected: boolean;
  onSelect: (e: ReactMouseEvent) => void;
}

function classNameFor(run: RunSummary): string {
  if (run.algorithm_class) return run.algorithm_class;
  if (run.root_agent_path) {
    const tail = run.root_agent_path.split(".").at(-1);
    if (tail) return tail;
  }
  return "Agent";
}

function statusTone(state: RunSummary["state"]): "live" | "ok" | "error" | "default" {
  if (state === "running") return "live";
  if (state === "error") return "error";
  if (state === "ended") return "ok";
  return "default";
}

export function RunRow({ run, active, selected, onSelect }: RunRowProps) {
  const className = classNameFor(run);
  const metric = getAlgorithmMetric(run);

  return (
    <li>
      <Link
        to={`/runs/${run.run_id}`}
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey) {
            e.preventDefault();
            onSelect(e);
          }
        }}
        className={cn(
          "group flex flex-col gap-0.5 border-l-2 border-transparent px-3 py-2 transition-colors duration-[var(--motion-quick)] ease-out",
          "hover:bg-bg-2",
          active && "border-l-accent bg-bg-2",
          selected && !active && "bg-bg-3",
        )}
      >
        <div className="flex items-center gap-2">
          <HashTag hash={run.run_id} dotOnly size="sm" />
          <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-text">
            {className}
          </span>
          {run.state === "running" ? (
            <Pill tone="live" pulse size="sm">
              live
            </Pill>
          ) : run.state === "error" ? (
            <Pill tone="error" size="sm">
              err
            </Pill>
          ) : null}
        </div>
        <div className="flex items-center gap-2 pl-[14px] text-[10px] text-muted-2">
          <span className="truncate font-mono">{truncateMiddle(run.run_id, 14)}</span>
          <span aria-hidden>·</span>
          <span className="flex-shrink-0">{formatRelativeTime(run.started_at)}</span>
          {metric !== "—" ? (
            <>
              <span aria-hidden className="ml-auto">
                ·
              </span>
              <span className="flex-shrink-0 truncate font-mono">{metric}</span>
            </>
          ) : null}
        </div>
        <span className="sr-only">{statusTone(run.state)}</span>
      </Link>
    </li>
  );
}
