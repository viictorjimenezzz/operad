import { EventRow, type EventRowModel, type FilteredEventKind, type NormalizedAgentEvent } from "@/components/agent-view/drawer/views/events/event-row";
import { LangfuseEmbed, buildLangfuseHref } from "@/components/agent-view/drawer/views/langfuse/langfuse-embed";
import { Chip } from "@/components/ui/chip";
import { EmptyState } from "@/components/ui/empty-state";
import { JsonView } from "@/components/ui/json-view";
import { SearchInput } from "@/components/ui/search-input";
import { useAgentEvents, useManifest } from "@/hooks/use-runs";
import type { AgentEventEnvelope, EventEnvelope } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";
import { useEventBufferStore } from "@/stores";
import { useUIStore } from "@/stores/ui";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

const EMPTY_EVENTS: EventEnvelope[] = [];
const KIND_OPTIONS: FilteredEventKind[] = ["start", "end", "chunk", "error"];

export function FilteredEvents({ runId, payload }: { runId: string; payload: Record<string, unknown> }) {
  const agentPath = typeof payload.agentPath === "string" ? payload.agentPath : null;
  const payloadInvocationId =
    typeof payload.invocationId === "string" ? payload.invocationId : null;
  const drawerWidth = useUIStore((s) => s.drawerWidth);
  const splitMode = drawerWidth >= 680;

  const [kindFilter, setKindFilter] = useState<FilteredEventKind | "all">("all");
  const [search, setSearch] = useState("");
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [isLivePulse, setIsLivePulse] = useState(false);
  const [selectedInvocationId, setSelectedInvocationId] = useState<string | null>(
    payloadInvocationId,
  );

  const parentRef = useRef<HTMLDivElement | null>(null);
  const prevLiveCount = useRef(0);

  const archived = useAgentEvents(runId || null, agentPath, 1_000);
  const liveRunEvents = useEventBufferStore((s) => s.eventsByRun.get(runId) ?? EMPTY_EVENTS);
  const manifest = useManifest();

  const liveAgentEvents = useMemo(
    () =>
      liveRunEvents.filter(
        (env): env is AgentEventEnvelope =>
          env.type === "agent_event" && (!!agentPath ? env.agent_path === agentPath : true),
      ),
    [agentPath, liveRunEvents],
  );

  useEffect(() => {
    if (liveAgentEvents.length <= prevLiveCount.current) return;
    prevLiveCount.current = liveAgentEvents.length;
    setIsLivePulse(true);
    const timer = window.setTimeout(() => setIsLivePulse(false), 700);
    return () => window.clearTimeout(timer);
  }, [liveAgentEvents.length]);

  const mergedEvents = useMemo(() => {
    const initial =
      archived.data?.events.filter(
        (env): env is AgentEventEnvelope =>
          env.type === "agent_event" && (!!agentPath ? env.agent_path === agentPath : true),
      ) ?? [];

    const seen = new Set<string>();
    const merged: NormalizedAgentEvent[] = [];

    for (const env of [...initial, ...liveAgentEvents]) {
      const normalized = normalizeEvent(env);
      if (seen.has(normalized.signature)) continue;
      seen.add(normalized.signature);
      merged.push(normalized);
    }

    merged.sort((a, b) => (a.started_at === b.started_at ? a.signature.localeCompare(b.signature) : a.started_at - b.started_at));
    return merged;
  }, [agentPath, archived.data?.events, liveAgentEvents]);

  const invocationOptions = useMemo(() => {
    if (!payloadInvocationId) return [];
    const ids: string[] = [];
    const seen = new Set<string>();

    if (!seen.has(payloadInvocationId)) {
      ids.push(payloadInvocationId);
      seen.add(payloadInvocationId);
    }

    for (const event of mergedEvents) {
      if (!event.invocationId || seen.has(event.invocationId)) continue;
      ids.push(event.invocationId);
      seen.add(event.invocationId);
    }

    return ids;
  }, [mergedEvents, payloadInvocationId]);

  useEffect(() => {
    if (!payloadInvocationId) {
      setSelectedInvocationId(null);
      return;
    }
    setSelectedInvocationId((prev) => prev ?? payloadInvocationId);
  }, [payloadInvocationId]);

  const rows = useMemo(() => {
    const filtered = mergedEvents.filter((event) => {
      if (kindFilter !== "all" && event.kind !== kindFilter) return false;
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        event.kind.toLowerCase().includes(q) ||
        event.agent_path.toLowerCase().includes(q) ||
        event.preview.toLowerCase().includes(q) ||
        event.signature.toLowerCase().includes(q)
      );
    });

    const grouped: EventRowModel[] = [];
    for (const event of filtered) {
      if (event.kind !== "chunk") {
        grouped.push(makeSingleRow(event));
        continue;
      }

      const prev = grouped[grouped.length - 1];
      const key = chunkKey(event);
      const prevFirstChunk = prev?.chunks?.[0];
      const prevKey = prevFirstChunk ? chunkKey(prevFirstChunk) : null;
      if (!prev || !prev.chunks || prevKey !== key) {
        grouped.push(makeChunkRow(event));
        continue;
      }
      prev.chunks.push(event);
      prev.preview = `${prev.chunks.length} chunks · ${event.preview}`;
      prev.latencyMs = event.latencyMs;
    }

    return grouped;
  }, [kindFilter, mergedEvents, search]);

  useEffect(() => {
    if (rows.length === 0) {
      setSelectedRowId(null);
      return;
    }
    const firstRow = rows[0];
    if (!firstRow) return;
    if (!selectedRowId || !rows.some((row) => row.id === selectedRowId)) {
      setSelectedRowId(firstRow.id);
    }
  }, [rows, selectedRowId]);

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => {
      const row = rows[index];
      if (!row) return 46;
      return row.chunks && expandedGroups.has(row.id) ? 88 : 46;
    },
    overscan: 10,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();
  const rowsToRender =
    virtualRows.length > 0
      ? virtualRows
      : rows.map((_, index) => ({ index, key: index, start: index * 46, size: 46 }));

  useEffect(() => {
    if (!selectedInvocationId) return;
    const targetIdx = rows.findIndex((row) => {
      if (row.event.invocationId === selectedInvocationId) return true;
      return !!row.chunks?.some((chunk) => chunk.invocationId === selectedInvocationId);
    });
    if (targetIdx < 0) return;
    rowVirtualizer.scrollToIndex(targetIdx, { align: "start" });
  }, [rowVirtualizer, rows, selectedInvocationId]);

  if (!runId) {
    return <EmptyState title="missing run id" description="open this drawer from a run page" />;
  }

  if (!agentPath) {
    return <EmptyState title="missing agent path" description="open this drawer from an agent edge" />;
  }

  if (archived.isLoading && mergedEvents.length === 0) {
    return <div className="p-3 text-xs text-muted">loading filtered events…</div>;
  }

  if (archived.error && mergedEvents.length === 0) {
    return <EmptyState title="failed to load events" description="check backend logs for /agent/{path}/events" />;
  }

  const selected = rows.find((row) => row.id === selectedRowId) ?? null;
  const langfuseUrl = manifest.data?.langfuseUrl ?? null;
  const openAllHref = langfuseUrl
    ? buildLangfuseHref(langfuseUrl, { agentPath }).href
    : null;

  const listPane = (
    <div className="grid min-h-0 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div className="flex min-h-0 flex-col overflow-hidden rounded-md border border-border bg-bg-1">
        <div className="border-b border-border px-2 py-1.5">
          <div className="mb-1 flex items-center gap-2">
            <span className="text-[11px] text-muted">{rows.length} events</span>
            <span className={`h-2 w-2 rounded-full ${isLivePulse ? "animate-pulse bg-ok" : "bg-muted-2"}`} />
            <span className="text-[11px] text-muted">live</span>
            {openAllHref ? (
              <button
                type="button"
                onClick={() => window.open(openAllHref, "_blank", "noopener")}
                className="ml-auto inline-flex items-center gap-1 rounded border border-border bg-bg-2 px-1.5 py-0.5 text-[10px] text-muted hover:text-text"
              >
                <ExternalLink size={11} />
                Open all in Langfuse
              </button>
            ) : null}
          </div>
          <div className="mb-1 flex items-center gap-1.5 overflow-auto">
            <Chip active={kindFilter === "all"} onClick={() => setKindFilter("all")}>all</Chip>
            {KIND_OPTIONS.map((kind) => (
              <Chip key={kind} active={kindFilter === kind} onClick={() => setKindFilter(kind)}>
                {kind}
              </Chip>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-1.5 md:grid-cols-[minmax(0,1fr)_auto]">
            <SearchInput value={search} onChange={setSearch} placeholder="search kind/path/preview" />
            {payloadInvocationId ? (
              <label className="flex items-center gap-1 text-[11px] text-muted">
                jump
                <select
                  value={selectedInvocationId ?? ""}
                  onChange={(e) => setSelectedInvocationId(e.target.value || null)}
                  className="rounded border border-border bg-bg-2 px-1.5 py-1 font-mono text-[11px] text-text"
                >
                  {invocationOptions.map((id, idx) => (
                    <option key={id} value={id}>
                      invocation #{idx + 1}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
        </div>

        {rows.length === 0 ? (
          <EmptyState title="no matching events" description="adjust filters or wait for new events" />
        ) : (
          <div ref={parentRef} className="min-h-0 flex-1 overflow-auto" data-testid="filtered-events-list">
            <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: "relative" }}>
              {rowsToRender.map((virtual) => {
                const row = rows[virtual.index];
                if (!row) return null;
                return (
                  <div
                    key={row.id}
                    data-index={virtual.index}
                    ref={rowVirtualizer.measureElement}
                    style={{
                      position: "absolute",
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtual.start}px)`,
                    }}
                  >
                    <EventRow
                      row={row}
                      selected={selectedRowId === row.id}
                      expanded={expandedGroups.has(row.id)}
                      relativeTime={formatRelativeTime(row.startedAt)}
                      onSelect={() => setSelectedRowId(row.id)}
                      {...(row.chunks
                        ? {
                            onToggleExpand: () => {
                              setExpandedGroups((prev) => {
                                const next = new Set(prev);
                                if (next.has(row.id)) next.delete(row.id);
                                else next.add(row.id);
                                return next;
                              });
                            },
                          }
                        : {})}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="min-h-0 overflow-auto rounded-md border border-border bg-bg-1 p-3">
        {selected ? (
          <div className="space-y-2 text-xs">
            <div className="font-mono text-muted">{selected.label}</div>
            <div className="text-[11px] text-muted">
              {selected.chunks ? `${selected.chunks.length} grouped chunks` : selected.kind}
            </div>
            <JsonView value={selected.chunks ? selected.chunks : selected.event} />
          </div>
        ) : (
          <EmptyState title="select an event" description="pick a row to inspect the full envelope" />
        )}
      </div>
    </div>
  );

  if (!splitMode) {
    return <div className="h-full p-3">{listPane}</div>;
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-0">
      <div className="min-h-0 border-r border-border p-3">{listPane}</div>
      <LangfuseEmbed runId={runId} payload={payload} className="h-full" />
    </div>
  );
}

function normalizeEvent(event: AgentEventEnvelope): NormalizedAgentEvent {
  const preview = previewForEvent(event);
  const signature = signatureForEvent(event);
  const invocationId = invocationIdFromMetadata(event.metadata);
  const latencyMs =
    event.finished_at != null && Number.isFinite(event.finished_at)
      ? Math.max(0, (event.finished_at - event.started_at) * 1000)
      : null;

  return {
    type: "agent_event",
    run_id: event.run_id,
    agent_path: event.agent_path,
    kind: event.kind,
    input: event.input ?? null,
    output: event.output ?? null,
    started_at: event.started_at,
    finished_at: event.finished_at ?? null,
    metadata: event.metadata ?? {},
    error: event.error ?? null,
    preview,
    signature,
    latencyMs,
    invocationId,
  };
}

function makeSingleRow(event: NormalizedAgentEvent): EventRowModel {
  return {
    id: event.signature,
    kind: event.kind,
    startedAt: event.started_at,
    label: event.agent_path,
    hash: event.signature,
    preview: event.preview,
    latencyMs: event.kind === "end" || event.kind === "error" ? event.latencyMs : null,
    event,
  };
}

function makeChunkRow(event: NormalizedAgentEvent): EventRowModel {
  return {
    id: `chunk-group:${event.signature}`,
    kind: "chunk",
    startedAt: event.started_at,
    label: `${event.agent_path} · stream`,
    hash: event.signature,
    preview: `1 chunk · ${event.preview}`,
    latencyMs: event.latencyMs,
    event,
    chunks: [event],
  };
}

function chunkKey(event: NormalizedAgentEvent): string {
  const meta = event.metadata;
  const streamId =
    asString(meta.stream_id) ??
    asString(meta.streamId) ??
    asString(meta.span_id) ??
    asString(meta.spanId) ??
    asString(meta.observation_id) ??
    event.invocationId ??
    "chunk";
  return `${event.agent_path}:${streamId}`;
}

function invocationIdFromMetadata(metadata: Record<string, unknown>): string | null {
  return (
    asString(metadata.invocation_id) ??
    asString(metadata.invocationId) ??
    asString(metadata.invocation) ??
    asString(metadata.call_id) ??
    null
  );
}

function previewForEvent(event: AgentEventEnvelope): string {
  if (event.kind === "start") {
    return truncatePreview(stringifyPreview(event.input));
  }
  if (event.kind === "end" || event.kind === "chunk") {
    return truncatePreview(stringifyPreview(event.output));
  }
  if (event.kind === "error") {
    if (event.error?.message) return truncatePreview(event.error.message);
    return truncatePreview(stringifyPreview(event.output));
  }
  return "";
}

function signatureForEvent(event: AgentEventEnvelope): string {
  return [
    event.run_id,
    event.agent_path,
    event.kind,
    event.started_at,
    event.finished_at,
    stableStringify(event.input),
    stableStringify(event.output),
    stableStringify(event.metadata),
    stableStringify(event.error),
  ].join("|");
}

function stringifyPreview(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function truncatePreview(value: string): string {
  if (value.length <= 120) return value;
  return `${value.slice(0, 117)}...`;
}

function stableStringify(value: unknown): string {
  if (value == null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (typeof value === "object") {
    const rec = value as Record<string, unknown>;
    const keys = Object.keys(rec).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(rec[k])}`).join(",")}}`;
  }
  return JSON.stringify(String(value));
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export {
  chunkKey,
  invocationIdFromMetadata,
  normalizeEvent,
  previewForEvent,
  signatureForEvent,
  stableStringify,
  truncatePreview,
};
