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
  onSelect: () => void;
};

export function AgentNodeCard({ data }: NodeProps) {
  const d = data as AgentNodeData;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        d.onSelect();
      }}
      className={cn(
        "nodrag nopan flex h-full w-full flex-col items-stretch gap-1 rounded-md border bg-bg-1 px-2.5 py-1.5 text-left transition-colors",
        d.selected
          ? "border-accent ring-1 ring-[--color-accent-dim]"
          : "border-border hover:border-border-strong",
        d.active && !d.selected ? "border-[--color-ok-dim]" : "",
        d.dimmed ? "opacity-30" : "opacity-100",
      )}
      style={{ minWidth: 0 }}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-muted-2" />
      <div className="flex items-center gap-1.5">
        <HashTag hash={d.hashContent ?? d.path} dotOnly size="sm" />
        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-text">
          {d.className}
        </span>
        {d.trainable ? <Flame size={10} className="text-[--color-warn]" /> : null}
        {d.active ? (
          <Activity size={10} className="animate-pulse text-[--color-ok]" />
        ) : null}
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
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-muted-2" />
    </button>
  );
}
