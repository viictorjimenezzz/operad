import { cn, formatRelativeTime } from "@/lib/utils";

export interface ValueTimelineRow {
  invocationId: string;
  startedAt: number;
  value: unknown;
  preview: string;
  isOutlier: boolean;
  tokenEstimate: number | null;
  repeated: boolean;
}

interface ValueRowProps {
  row: ValueTimelineRow;
  nowSec: number;
  selected: boolean;
  selectedInvocation: boolean;
  checkedForDiff: boolean;
  onToggleDiff: (invocationId: string) => void;
  onSelect: () => void;
  onOpenInvocation: () => void;
  onFindSimilar: () => void;
  onCopy: () => void;
}

export function ValueRow({
  row,
  nowSec,
  selected,
  selectedInvocation,
  checkedForDiff,
  onToggleDiff,
  onSelect,
  onOpenInvocation,
  onFindSimilar,
  onCopy,
}: ValueRowProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-[26px_86px_1fr_auto] gap-2 border-b border-border/50 px-2 py-1.5 text-xs",
        row.repeated ? "bg-accent-dim/30" : "",
        selected ? "bg-bg-2" : "hover:bg-bg-2/70",
        selectedInvocation ? "ring-1 ring-accent ring-inset" : "",
      )}
    >
      <input
        aria-label={`select diff ${row.invocationId}`}
        type="checkbox"
        checked={checkedForDiff}
        onChange={() => onToggleDiff(row.invocationId)}
        className="mt-0.5 h-3.5 w-3.5"
      />
      <button
        type="button"
        className="font-mono text-[11px] text-muted"
        title={new Date(row.startedAt * 1000).toLocaleString()}
        onClick={onSelect}
      >
        {formatRelativeTime(row.startedAt, nowSec)}
      </button>
      <button type="button" className="min-w-0 text-left" onClick={onSelect}>
        <span className="font-mono text-[11px] text-text" title={row.preview}>
          {row.preview}
        </span>
        <span className="ml-2 text-[10px] text-muted">
          {row.isOutlier ? "outlier" : ""}
          {row.tokenEstimate != null ? ` · ~${row.tokenEstimate} tok` : ""}
        </span>
      </button>
      <span className="flex items-center gap-1">
        <button
          type="button"
          className="rounded border border-border bg-bg-1 px-1.5 py-0.5 text-[10px] text-muted hover:text-text"
          onClick={onOpenInvocation}
        >
          open
        </button>
        <button
          type="button"
          className="rounded border border-border bg-bg-1 px-1.5 py-0.5 text-[10px] text-muted hover:text-text"
          onClick={onFindSimilar}
        >
          similar
        </button>
        <button
          type="button"
          className="rounded border border-border bg-bg-1 px-1.5 py-0.5 text-[10px] text-muted hover:text-text"
          onClick={onCopy}
        >
          copy
        </button>
      </span>
    </div>
  );
}
