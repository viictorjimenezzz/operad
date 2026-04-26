import { hashToColor } from "@/lib/hash-color";
import type { AgentInvocation } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";
import { useUIStore } from "@/stores";
import { useMemo } from "react";

interface DriftStripProps {
  agentPath: string;
  invocations: AgentInvocation[];
}

export function DriftStrip({ agentPath, invocations }: DriftStripProps) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  const uniquePrompts = useMemo(
    () => new Set(invocations.map((row) => row.hash_prompt ?? "none")).size,
    [invocations],
  );

  if (invocations.length === 0) {
    return (
      <div className="rounded border border-border bg-bg-2 px-2 py-2 text-[11px] text-muted">
        no invocation drift yet
      </div>
    );
  }

  return (
    <div className="rounded border border-border bg-bg-2 p-2">
      <div className="flex h-4 items-stretch overflow-hidden rounded border border-border">
        {invocations.map((row, idx) => {
          const isTransition = idx > 0 && invocations[idx - 1]?.hash_prompt !== row.hash_prompt;
          return (
            <button
              key={row.id}
              type="button"
              className="relative h-full flex-1 border-r border-bg last:border-r-0"
              style={{ backgroundColor: hashToColor(row.hash_prompt ?? `none:${idx}`, 0.8) }}
              title={`#${idx + 1} • ${row.hash_prompt ?? "no hash"}`}
              onClick={() => {
                if (!isTransition) return;
                openDrawer("prompts", { agentPath, focus: row.id });
              }}
            >
              {isTransition ? (
                <span className="absolute inset-y-0 left-0 w-[2px] bg-text/90" />
              ) : null}
            </button>
          );
        })}
      </div>
      <div className="mt-1 text-[11px] text-muted">
        {invocations.length} invocations · {uniquePrompts} unique prompts · last{" "}
        {formatRelativeTime(invocations.at(-1)?.started_at ?? null)}
      </div>
    </div>
  );
}
