import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { AgentInvocation, AgentInvocationsResponse } from "@/lib/types";
import { cn, formatDurationMs, formatRelativeTime, formatTokens } from "@/lib/utils";
import { useUIStore } from "@/stores";
import { ExternalLink } from "lucide-react";

interface InvocationsTableProps {
  data: AgentInvocationsResponse | null | undefined;
  live?: boolean;
}

function latencyTone(ms: number | null): string {
  if (ms == null) return "text-muted";
  if (ms < 1000) return "text-ok";
  if (ms < 5000) return "text-warn";
  return "text-err";
}

function RowActions({ row }: { row: AgentInvocation }) {
  const openDrawer = useUIStore((s) => s.openDrawer);
  const agentPath = row.id.split(":")[0] ?? "root";
  return (
    <div className="flex items-center gap-1">
      <Button
        size="sm"
        variant="ghost"
        className="h-6 px-1.5"
        onClick={() => openDrawer("values", { agentPath, side: "in" })}
      >
        view I/O
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="h-6 px-1.5"
        onClick={() => openDrawer("prompts", { agentPath, focus: row.id })}
      >
        diff
      </Button>
      {row.langfuse_url ? (
        <a
          href={row.langfuse_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-6 items-center rounded border border-border px-1.5 text-muted hover:text-text"
          title="open in langfuse"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : null}
    </div>
  );
}

export function InvocationsTable({ data, live = false }: InvocationsTableProps) {
  const rows = data?.invocations ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState
        title="waiting for first invocation"
        description="rows will appear once the run starts invoking"
      />
    );
  }

  return (
    <div className="overflow-auto rounded border border-border">
      <table className="w-full min-w-[920px] border-collapse text-xs">
        <thead>
          <tr className="bg-bg-2 text-left text-muted">
            <th className="px-2 py-1.5">#</th>
            <th className="px-2 py-1.5">started</th>
            <th className="px-2 py-1.5">latency</th>
            <th className="px-2 py-1.5">tokens</th>
            <th className="px-2 py-1.5">prompt hash</th>
            <th className="px-2 py-1.5">status</th>
            <th className="px-2 py-1.5">actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr
              key={row.id}
              className={cn(
                "border-t border-border",
                live && idx === rows.length - 1 ? "animate-pulse" : undefined,
              )}
            >
              <td className="px-2 py-1.5 text-muted">{idx + 1}</td>
              <td className="px-2 py-1.5" title={new Date(row.started_at * 1000).toISOString()}>
                {formatRelativeTime(row.started_at)}
              </td>
              <td className={cn("px-2 py-1.5 font-mono", latencyTone(row.latency_ms))}>
                {formatDurationMs(row.latency_ms)}
              </td>
              <td className="px-2 py-1.5 font-mono">
                {formatTokens(row.prompt_tokens)} / {formatTokens(row.completion_tokens)}
              </td>
              <td className="px-2 py-1.5">
                <HashChip value={row.hash_prompt} />
              </td>
              <td className="px-2 py-1.5">
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[11px] uppercase",
                    row.status === "ok" ? "bg-ok-dim text-ok" : "bg-err-dim text-err",
                  )}
                  title={row.error ?? undefined}
                >
                  {row.status}
                </span>
              </td>
              <td className="px-2 py-1.5">
                <RowActions row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
