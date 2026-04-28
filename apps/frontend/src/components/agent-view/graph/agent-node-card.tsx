import { HashTag } from "@/components/ui";
import { cn } from "@/lib/utils";
import { Handle, type NodeProps, Position } from "@xyflow/react";
import { Activity, Flame } from "lucide-react";

export type AgentNodeData = {
  path: string;
  className: string;
  inputLabel: string;
  outputLabel: string;
  selected: boolean;
  dimmed: boolean;
  active: boolean;
  trainable: boolean;
  hashContent: string | null;
  invocationCount: number;
};

// Click is handled at the React Flow level via `onNodeClick`. Keeping this
// component free of inline event-handler closures is what lets the
// `nodes` array stay referentially stable across renders, which is the
// fix for the React #185 max-update-depth loop the previous build had.
export function AgentNodeCard({ data }: NodeProps) {
  const d = data as AgentNodeData;
  return (
    <div
      className={cn(
        "flex h-full w-full cursor-pointer flex-col items-stretch gap-1 rounded-md border bg-bg-2 px-2.5 py-1.5 text-left shadow-[var(--shadow-card-raised)] transition-colors hover:bg-bg-3",
        d.selected
          ? "border-accent ring-1 ring-[--color-accent-dim]"
          : "border-border-strong hover:border-accent/70",
        d.active && !d.selected ? "border-[--color-ok-dim]" : "",
        d.dimmed ? "opacity-60" : "opacity-100",
      )}
      style={{ minWidth: 0 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2.5 !w-2.5 !border-0 !bg-accent"
      />
      <div className="flex items-center gap-1.5">
        <HashTag hash={d.hashContent ?? d.path} dotOnly size="sm" />
        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-text">
          {d.className}
        </span>
        {d.trainable ? <Flame size={10} className="text-[--color-warn]" /> : null}
        {d.active ? <Activity size={10} className="animate-pulse text-[--color-ok]" /> : null}
      </div>
      <div className="flex items-center justify-between font-mono text-[10px] text-muted-2">
        <span className="truncate" title={d.inputLabel}>
          {d.inputLabel}
        </span>
        <span className="px-1 text-muted-2">→</span>
        <span className="truncate" title={d.outputLabel}>
          {d.outputLabel}
        </span>
      </div>
      {d.invocationCount > 0 ? (
        <div className="text-right font-mono text-[9px] tabular-nums text-muted-2">
          {d.invocationCount}× invocations
        </div>
      ) : null}
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2.5 !w-2.5 !border-0 !bg-accent"
      />
    </div>
  );
}
