import { HashTag } from "@/components/ui";
import { cn, formatDurationMs, formatTokens } from "@/lib/utils";
import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getBezierPath } from "@xyflow/react";
import { Activity, Flame } from "lucide-react";

export type AgentEdgeCardData = {
  agentPath: string;
  className: string;
  classKind: "leaf" | "composite";
  selected: boolean;
  dimmed: boolean;
  active: boolean;
  trainable: boolean;
  hookOverride: boolean;
  cassette: boolean;
  hashContent: string | null;
  latencyMs: number | null;
  tokens: number | null;
  invocationCount: number;
  onSelect: () => void;
};

export function AgentEdgeCard({
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
  const d = data as AgentEdgeCardData;
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
        : "var(--color-chunk)";

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        {...(typeof markerEnd === "string" ? { markerEnd } : {})}
        style={{
          stroke,
          strokeWidth: d.selected ? 2.4 : d.active ? 2 : 1.4,
          opacity: d.dimmed ? 0.25 : 1,
          strokeDasharray: d.active ? "6 6" : undefined,
        }}
        className={d.active ? "animate-[dash_1.4s_linear_infinite]" : undefined}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          aria-label={`agent ${d.className} (${d.agentPath})`}
          onClick={(e) => {
            e.stopPropagation();
            d.onSelect();
          }}
          className={cn(
            "nodrag nopan absolute flex w-[170px] -translate-x-1/2 -translate-y-1/2 flex-col gap-1 rounded-xl border px-3 py-2 text-left transition-all duration-[var(--motion-quick)]",
            "shadow-[var(--shadow-card-soft)] backdrop-blur-sm",
            d.selected
              ? "border-accent bg-bg-1 ring-2 ring-[--color-accent-dim]"
              : "border-border bg-bg-1 hover:border-border-strong",
            d.active && !d.selected ? "border-[--color-ok-dim]" : "",
            d.dimmed ? "opacity-30" : "opacity-100",
          )}
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: "all",
          }}
        >
          <div className="flex items-center gap-1.5">
            <HashTag hash={d.hashContent ?? d.agentPath} dotOnly size="sm" />
            <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-text">
              {d.className}
            </span>
            {d.classKind === "composite" ? (
              <span className="text-[9px] uppercase tracking-[0.06em] text-muted-2">comp</span>
            ) : null}
          </div>
          <div className="flex items-center gap-2 font-mono text-[10px] text-muted">
            <span className="tabular-nums">{formatDurationMs(d.latencyMs)}</span>
            {d.tokens != null ? (
              <>
                <span aria-hidden className="text-muted-2">
                  ·
                </span>
                <span className="tabular-nums">{formatTokens(d.tokens)}t</span>
              </>
            ) : null}
            {d.invocationCount > 0 ? (
              <>
                <span aria-hidden className="text-muted-2">
                  ·
                </span>
                <span className="tabular-nums">{d.invocationCount}×</span>
              </>
            ) : null}
            <span className="ml-auto flex items-center gap-1">
              {d.trainable ? (
                <Flame size={10} className="text-[--color-warn]" aria-label="trainable" />
              ) : null}
              {d.hookOverride ? (
                <span
                  aria-label="forward hook overridden"
                  title="forward_in / forward_out hook overridden"
                  className="inline-block h-1.5 w-1.5 rounded-full bg-[--color-algo]"
                />
              ) : null}
              {d.active ? (
                <Activity size={10} className="text-[--color-ok] animate-pulse" aria-label="live" />
              ) : null}
            </span>
          </div>
        </button>
      </EdgeLabelRenderer>
    </>
  );
}
