import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { RunSummary } from "@/lib/types";
import { cn, formatDurationMs, formatRelativeTime, formatTokens } from "@/lib/utils";
import { useUIStore } from "@/stores/ui";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";

const InvocationRowSchema = z.object({
  id: z.string(),
  started_at: z.number().nullable().optional(),
  finished_at: z.number().nullable().optional(),
  latency_ms: z.number().nullable().optional(),
  prompt_tokens: z.number().nullable().optional(),
  completion_tokens: z.number().nullable().optional(),
  hash_prompt: z.string().nullable().optional(),
  hash_input: z.string().nullable().optional(),
  hash_content: z.string().nullable().optional(),
  status: z.enum(["ok", "error"]).optional(),
  error: z.string().nullable().optional(),
  langfuse_url: z.string().nullable().optional(),
  script: z.string().nullable().optional(),
  input: z.unknown().optional(),
  output: z.unknown().optional(),
});

const InvocationsPayload = z.object({
  agent_path: z.string().default(""),
  invocations: z.array(InvocationRowSchema).default([]),
});

type InvocationRow = z.infer<typeof InvocationRowSchema>;

function latencyClass(latencyMs: number | null | undefined): string {
  if (latencyMs == null || !Number.isFinite(latencyMs)) return "text-muted";
  if (latencyMs < 1_000) return "text-ok";
  if (latencyMs < 5_000) return "text-warn";
  return "text-err";
}

function absoluteTime(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return "unknown time";
  return new Date(ts * 1000).toLocaleString();
}

function renderStatus(row: InvocationRow) {
  if (row.status === "error") {
    return (
      <span title={row.error ?? "error"}>
        <Badge variant="error">error</Badge>
      </span>
    );
  }
  return <Badge variant="ended">ok</Badge>;
}

interface InvocationsTableProps {
  summary: unknown;
  invocations: unknown;
}

export function InvocationsTable({ summary, invocations }: InvocationsTableProps) {
  const summaryParsed = RunSummary.safeParse(summary);
  const invParsed = InvocationsPayload.safeParse(invocations);
  const openDrawer = useUIStore((s) => s.openDrawer);
  const setSelectedInvocation = useUIStore((s) => s.setSelectedInvocation);
  const selectedInvocationId = useUIStore((s) => s.selectedInvocationId);
  const selectedInvocationAgentPath = useUIStore((s) => s.selectedInvocationAgentPath);
  const comparisonInvocationId = useUIStore((s) => s.comparisonInvocationId);
  const comparisonInvocationAgentPath = useUIStore((s) => s.comparisonInvocationAgentPath);
  const setComparisonInvocation = useUIStore((s) => s.setComparisonInvocation);
  const clearComparisonInvocation = useUIStore((s) => s.clearComparisonInvocation);

  const run = summaryParsed.success ? summaryParsed.data : null;
  const agentPath = invParsed.success ? invParsed.data.agent_path : "";
  const rows = invParsed.success ? invParsed.data.invocations : [];

  const [nowSec, setNowSec] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (run?.state !== "running") return;
    const id = window.setInterval(() => setNowSec(Date.now() / 1000), 5_000);
    return () => window.clearInterval(id);
  }, [run?.state]);

  const [pulseIds, setPulseIds] = useState<Set<string>>(new Set());
  const prevRowCount = useRef(rows.length);
  useEffect(() => {
    if (run?.state !== "running") {
      prevRowCount.current = rows.length;
      return;
    }
    if (rows.length <= prevRowCount.current) return;
    const fresh = rows.slice(prevRowCount.current).map((r) => r.id);
    prevRowCount.current = rows.length;
    setPulseIds((prev) => {
      const next = new Set(prev);
      for (const id of fresh) next.add(id);
      return next;
    });
    const t = window.setTimeout(() => {
      setPulseIds((prev) => {
        const next = new Set(prev);
        for (const id of fresh) next.delete(id);
        return next;
      });
    }, 1_200);
    return () => window.clearTimeout(t);
  }, [rows, run?.state]);

  const [hovered, setHovered] = useState<InvocationRow | null>(null);

  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 38,
    overscan: 8,
  });

  const virtualRows = rowVirtualizer.getVirtualItems();
  const rowsToRender =
    virtualRows.length > 0
      ? virtualRows
      : rows.map((_, index) => ({ index, key: index, start: index * 38, size: 38 }));

  const rowsByIndex = useMemo(() => rows, [rows]);

  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-border bg-bg-1 p-3">
        <EmptyState title="waiting for first invocation" />
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-bg-1">
      <div className="grid grid-cols-[56px_120px_90px_120px_110px_80px_1fr] gap-2 border-b border-border px-3 py-2 text-[10px] uppercase tracking-[0.09em] text-muted">
        <span>#</span>
        <span>started</span>
        <span>latency</span>
        <span>tokens</span>
        <span>prompt</span>
        <span>status</span>
        <span>actions</span>
      </div>
      <div ref={parentRef} className="max-h-[320px] overflow-auto" data-testid="invocations-scroll">
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: "relative" }}>
          {rowsToRender.map((virtual) => {
            const row = rowsByIndex[virtual.index];
            if (!row) return null;
            const relative = formatRelativeTime(row.started_at ?? null, nowSec);
            return (
              <button
                type="button"
                key={row.id}
                data-testid={`invocation-row-${virtual.index}`}
                className={cn(
                  "grid cursor-pointer grid-cols-[56px_120px_90px_120px_110px_80px_1fr] items-center gap-2 border-b border-border/60 px-3 py-2 text-xs hover:bg-bg-2",
                  pulseIds.has(row.id) ? "animate-pulse" : "",
                  selectedInvocationId === row.id && selectedInvocationAgentPath === agentPath
                    ? "ring-1 ring-accent ring-inset"
                    : "",
                )}
                style={{
                  position: "absolute",
                  left: 0,
                  top: 0,
                  transform: `translateY(${virtual.start}px)`,
                  width: "100%",
                  height: `${virtual.size}px`,
                }}
                onMouseEnter={() => setHovered(row)}
                onFocus={() => setHovered(row)}
                onClick={() => {
                  setSelectedInvocation(row.id, agentPath);
                  openDrawer("events", {
                    agentPath,
                    invocationId: row.id,
                    hashPrompt: row.hash_prompt ?? undefined,
                  });
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedInvocation(row.id, agentPath);
                    openDrawer("events", {
                      agentPath,
                      invocationId: row.id,
                      hashPrompt: row.hash_prompt ?? undefined,
                    });
                  }
                }}
              >
                <span className="font-mono text-muted">{virtual.index + 1}</span>
                <span className="font-mono" title={absoluteTime(row.started_at)}>
                  {relative}
                </span>
                <span className={cn("font-mono", latencyClass(row.latency_ms))}>
                  {formatDurationMs(row.latency_ms)}
                </span>
                <span className="font-mono text-muted">
                  {formatTokens(row.prompt_tokens)} / {formatTokens(row.completion_tokens)}
                </span>
                <HashChip hash={row.hash_prompt} asButton={false} />
                {renderStatus(row)}
                <span className="flex items-center gap-1">
                  <button
                    type="button"
                    className={cn(
                      "rounded border border-border bg-bg-2 px-1.5 py-0.5 text-[11px] text-muted hover:text-text",
                      comparisonInvocationAgentPath === agentPath &&
                        comparisonInvocationId === row.id
                        ? "text-accent"
                        : "",
                    )}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedInvocation(row.id, agentPath);
                      openDrawer("events", {
                        agentPath,
                        invocationId: row.id,
                        hashPrompt: row.hash_prompt ?? undefined,
                      });
                    }}
                  >
                    I/O
                  </button>
                  <button
                    type="button"
                    className="rounded border border-border bg-bg-2 px-1.5 py-0.5 text-[11px] text-muted hover:text-text"
                    onClick={(e) => {
                      e.stopPropagation();
                      const hasAnchor =
                        comparisonInvocationAgentPath === agentPath && !!comparisonInvocationId;
                      if (!hasAnchor || !comparisonInvocationId) {
                        setComparisonInvocation(row.id, agentPath);
                        return;
                      }
                      if (comparisonInvocationId === row.id) {
                        clearComparisonInvocation();
                        return;
                      }
                      openDrawer("diff", {
                        agentPath,
                        fromInvocationId: comparisonInvocationId,
                        toInvocationId: row.id,
                      });
                      clearComparisonInvocation();
                    }}
                  >
                    diff
                  </button>
                  <button
                    type="button"
                    className="rounded border border-border bg-bg-2 px-1.5 py-0.5 text-[11px] text-muted hover:text-text"
                    onClick={(e) => {
                      e.stopPropagation();
                      openDrawer("experiment", {
                        agentPath,
                        input: row.input ?? {},
                        invocationId: row.id,
                      });
                    }}
                  >
                    run again
                  </button>
                  {row.langfuse_url ? (
                    <a
                      href={row.langfuse_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="rounded p-1 text-muted hover:text-text"
                      aria-label="Open invocation in Langfuse"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : null}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      <div className="border-t border-border px-3 py-2">
        {hovered ? (
          <div className="grid grid-cols-1 gap-2 text-[11px] text-muted md:grid-cols-2">
            <div className="rounded border border-border bg-bg-2 p-2">
              <div className="mb-1 uppercase tracking-[0.08em] text-muted-2">input preview</div>
              <div className="font-mono">hash_input: {hovered.hash_input ?? "—"}</div>
              <div className="font-mono">script: {hovered.script ?? "—"}</div>
            </div>
            <div className="rounded border border-border bg-bg-2 p-2">
              <div className="mb-1 uppercase tracking-[0.08em] text-muted-2">output preview</div>
              <div className="font-mono">status: {hovered.status ?? "ok"}</div>
              <div className="font-mono">error: {hovered.error ?? "—"}</div>
            </div>
          </div>
        ) : (
          <span className="text-[11px] text-muted">hover a row to preview invocation metadata</span>
        )}
      </div>
    </div>
  );
}
