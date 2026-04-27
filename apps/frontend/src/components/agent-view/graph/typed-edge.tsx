import { cn } from "@/lib/utils";
import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getBezierPath } from "@xyflow/react";

export type TypedEdgeData = {
  type: string;
  selected: boolean;
  dimmed: boolean;
  active: boolean;
};

export function TypedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
}: EdgeProps) {
  const d = (data as TypedEdgeData) ?? { type: "", selected: false, dimmed: false, active: false };
  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const stroke = d.dimmed
    ? "var(--color-border)"
    : d.selected
      ? "var(--color-accent)"
      : d.active
        ? "var(--color-ok)"
        : "var(--color-muted-2)";

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        {...(typeof markerEnd === "string" ? { markerEnd } : {})}
        style={{
          stroke,
          strokeWidth: d.selected ? 2 : 1.2,
          opacity: d.dimmed ? 0.25 : 1,
          strokeDasharray: d.active ? "5 5" : undefined,
        }}
      />
      {d.type ? (
        <EdgeLabelRenderer>
          <div
            className={cn(
              "nodrag nopan absolute -translate-x-1/2 -translate-y-1/2 rounded border border-border bg-bg px-1.5 py-0.5 font-mono text-[10px] tabular-nums",
              d.dimmed ? "text-muted-2 opacity-50" : "text-muted",
            )}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "none",
            }}
          >
            {d.type}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
