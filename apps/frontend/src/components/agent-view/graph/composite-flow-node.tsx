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
          "flex h-full w-full cursor-pointer flex-col rounded-md border border-dashed bg-bg-1/40 transition-colors",
          d.selected ? "border-accent" : "border-[--color-algo]/40",
          d.dimmed ? "opacity-30" : "opacity-100",
        )}
      >
        <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-muted-2" />
        <div className="flex h-7 items-center gap-1.5 border-b border-[--color-algo]/30 bg-[--color-algo-dim]/30 px-2 text-left text-[11px] font-semibold uppercase tracking-[0.06em] text-[--color-algo]">
          <ChevronDown size={11} />
          <span className="truncate">{d.className}</span>
          <span className="ml-auto font-mono text-[10px] normal-case tracking-normal text-muted">
            {d.childCount} child{d.childCount === 1 ? "" : "ren"}
          </span>
        </div>
        <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-muted-2" />
      </div>
    );
  }
  return (
    <div
      className={cn(
        "flex h-full w-full cursor-pointer flex-col gap-0.5 rounded-md border bg-[--color-algo-dim]/40 px-2.5 py-1.5 text-left transition-colors",
        d.selected
          ? "border-[--color-algo] ring-1 ring-[--color-algo]/30"
          : "border-[--color-algo]/40 hover:border-[--color-algo]",
        d.dimmed ? "opacity-30" : "opacity-100",
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-muted-2" />
      <div className="flex items-center gap-1.5">
        <ChevronRight size={11} className="text-[--color-algo]" />
        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold uppercase tracking-[0.04em] text-[--color-algo]">
          {d.className}
        </span>
      </div>
      <div className="font-mono text-[10px] text-muted">
        {d.childCount} child{d.childCount === 1 ? "" : "ren"} · double-click to expand
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-muted-2" />
    </div>
  );
}
