import { cn } from "@/lib/utils";
import { Handle, type NodeProps, Position } from "@xyflow/react";
import { ChevronDown, ChevronRight } from "lucide-react";

export type CompositeNodeData = {
  path: string;
  className: string;
  expanded: boolean;
  selected: boolean;
  dimmed: boolean;
  childCount: number;
};

// Click handling lives at the React Flow level via `onNodeClick` /
// `onNodeDoubleClick` so the `nodes` data prop never embeds new
// closures per render. See agent-flow-graph.tsx for the rationale.
export function CompositeFlowNode({ data }: NodeProps) {
  const d = data as CompositeNodeData;
  if (d.expanded) {
    return (
      <div
        className={cn(
          "flex h-full w-full cursor-pointer flex-col rounded-md border bg-bg-2 shadow-[var(--shadow-card-raised)] transition-colors hover:bg-bg-3",
          d.selected ? "border-accent ring-1 ring-[--color-accent-dim]" : "border-border-strong",
          d.dimmed ? "opacity-60" : "opacity-100",
        )}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="!h-2.5 !w-2.5 !border-0 !bg-[--color-algo]"
        />
        <div className="flex h-7 items-center gap-1.5 border-b border-border-strong bg-bg-3 px-2 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-text">
          <ChevronDown size={11} />
          <span className="truncate">{d.className}</span>
          <span className="ml-auto font-mono text-[10px] normal-case tracking-normal text-muted">
            {d.childCount} child{d.childCount === 1 ? "" : "ren"}
          </span>
        </div>
        <Handle
          type="source"
          position={Position.Right}
          className="!h-2.5 !w-2.5 !border-0 !bg-[--color-algo]"
        />
      </div>
    );
  }
  return (
    <div
      className={cn(
        "flex h-full w-full cursor-pointer flex-col gap-0.5 rounded-md border bg-bg-2 px-2.5 py-1.5 text-left shadow-[var(--shadow-card-raised)] transition-colors hover:bg-bg-3",
        d.selected
          ? "border-accent ring-1 ring-[--color-accent-dim]"
          : "border-border-strong hover:border-[--color-algo]",
        d.dimmed ? "opacity-60" : "opacity-100",
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2.5 !w-2.5 !border-0 !bg-[--color-algo]"
      />
      <div className="flex items-center gap-1.5">
        <ChevronRight size={11} className="text-[--color-algo]" />
        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold uppercase tracking-[0.04em] text-[--color-algo]">
          {d.className}
        </span>
      </div>
      <div className="font-mono text-[10px] text-muted">
        {d.childCount} child{d.childCount === 1 ? "" : "ren"} · double-click to expand
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2.5 !w-2.5 !border-0 !bg-[--color-algo]"
      />
    </div>
  );
}
