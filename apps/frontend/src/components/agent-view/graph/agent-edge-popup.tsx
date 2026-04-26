import { ConfigSection } from "@/components/agent-view/graph/config-section";
import { Button } from "@/components/ui/button";
import type { AgentInvocationsResponse, AgentMetaResponse } from "@/lib/types";
import { formatDurationMs } from "@/lib/utils";

interface AgentEdgePopupProps {
  agentPath: string;
  meta: AgentMetaResponse | null | undefined;
  invocations: AgentInvocationsResponse | null | undefined;
  onOpenLangfuse: () => void;
  onOpenEvents: () => void;
  onOpenPrompts: () => void;
  onClose: () => void;
}

export function AgentEdgePopup({
  agentPath,
  meta,
  invocations,
  onOpenLangfuse,
  onOpenEvents,
  onOpenPrompts,
  onClose,
}: AgentEdgePopupProps) {
  const rows = invocations?.invocations ?? [];
  const avgLatency = rows.length
    ? rows.reduce((sum, row) => sum + (row.latency_ms ?? 0), 0) / rows.length
    : null;

  return (
    <dialog open className="w-[320px] space-y-2 rounded border border-border bg-bg-1 p-2 shadow-xl">
      <div className="flex items-center justify-between">
        <div className="text-xs text-text">{meta?.class_name ?? agentPath}</div>
        <Button variant="ghost" size="sm" className="h-5 px-1" onClick={onClose}>
          close
        </Button>
      </div>

      <ConfigSection config={(meta?.config ?? null) as Record<string, unknown> | null} />

      <div className="rounded border border-border bg-bg-2 p-2">
        <div className="mb-1 text-[11px] text-muted">links</div>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-1.5 text-[11px]"
            onClick={onOpenLangfuse}
          >
            langfuse
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-1.5 text-[11px]"
            onClick={onOpenEvents}
          >
            events
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-1.5 text-[11px]"
            onClick={onOpenPrompts}
          >
            prompts
          </Button>
        </div>
      </div>

      <div className="rounded border border-border bg-bg-2 p-2 text-[11px]">
        <div className="mb-1 text-muted">at a glance</div>
        <div className="grid grid-cols-2 gap-1">
          <span className="text-muted">invocations</span>
          <span className="text-text">{rows.length}</span>
          <span className="text-muted">avg latency</span>
          <span className="text-text">{formatDurationMs(avgLatency)}</span>
          <span className="text-muted">hash content</span>
          <code className="truncate text-text">{meta?.hash_content ?? "—"}</code>
        </div>
      </div>
    </dialog>
  );
}
