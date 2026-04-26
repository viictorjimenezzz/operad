import { AgentEdgePopup } from "@/components/agent-view/graph/agent-edge-popup";
import { dashboardApi } from "@/lib/api/dashboard";
import { useUIStore } from "@/stores";
import { useQuery } from "@tanstack/react-query";
import { BaseEdge, EdgeLabelRenderer, type EdgeProps, getBezierPath } from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";

type AgentEdgeData = {
  runId: string;
  agentPath: string;
  label: string;
  selected: boolean;
  dimmed: boolean;
  onSelect: () => void;
  onClose: () => void;
};

export function AgentEdge({
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
  const d = data as AgentEdgeData;
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const openDrawer = useUIStore((s) => s.openDrawer);

  const [hovered, setHovered] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    if (!hovered) {
      setShowPreview(false);
      return;
    }
    const timer = setTimeout(() => setShowPreview(true), 300);
    return () => clearTimeout(timer);
  }, [hovered]);

  const metaQuery = useQuery({
    queryKey: ["edge-meta", d.runId, d.agentPath],
    queryFn: () => dashboardApi.agentMeta(d.runId, d.agentPath),
    enabled: d.selected,
    staleTime: 30_000,
  });

  const invocationsQuery = useQuery({
    queryKey: ["edge-invocations", d.runId, d.agentPath],
    queryFn: () => dashboardApi.agentInvocations(d.runId, d.agentPath),
    enabled: d.selected,
    staleTime: 30_000,
  });
  const parametersQuery = useQuery({
    queryKey: ["edge-parameters", d.runId, d.agentPath],
    queryFn: () => dashboardApi.agentParameters(d.runId, d.agentPath),
    enabled: d.selected,
    staleTime: 30_000,
  });

  const stroke = useMemo(() => {
    if (d.dimmed) return "var(--color-border)";
    return d.selected ? "var(--color-accent)" : "var(--color-chunk)";
  }, [d.dimmed, d.selected]);

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        {...(typeof markerEnd === "string" ? { markerEnd } : {})}
        style={{ stroke, strokeWidth: d.selected ? 2.4 : 1.5, opacity: d.dimmed ? 0.2 : 1 }}
      />
      <EdgeLabelRenderer>
        <div
          className="nodrag nopan absolute"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: "all",
          }}
        >
          <button
            type="button"
            className="rounded border border-border bg-bg-1 px-1.5 py-0.5 text-[11px] text-text"
            onClick={d.onSelect}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            aria-label={`agent edge ${d.label}`}
          >
            {d.label}
          </button>

          {showPreview && !d.selected ? (
            <div className="absolute left-1/2 top-full z-20 mt-1 w-56 -translate-x-1/2 rounded border border-border bg-bg-1 p-1.5 text-[10px] text-muted shadow-lg">
              <div>{d.label}</div>
              <div>{d.agentPath}</div>
            </div>
          ) : null}

          {d.selected ? (
            <div className="absolute left-1/2 top-full z-20 mt-2 -translate-x-1/2">
              <AgentEdgePopup
                agentPath={d.agentPath}
                meta={metaQuery.data ?? null}
                invocations={invocationsQuery.data ?? null}
                parameters={parametersQuery.data ?? null}
                onOpenLangfuse={() => openDrawer("langfuse", { agentPath: d.agentPath })}
                onOpenEvents={() => openDrawer("events", { agentPath: d.agentPath })}
                onOpenPrompts={() => openDrawer("prompts", { agentPath: d.agentPath })}
                onOpenExperiment={() => openDrawer("experiment", { agentPath: d.agentPath })}
                onOpenGradient={(paramPath) =>
                  openDrawer("gradients", { agentPath: d.agentPath, paramPath })
                }
                onOpenExperiment={() => openDrawer("experiment", { agentPath: d.agentPath })}
                onClose={d.onClose}
              />
            </div>
          ) : null}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
