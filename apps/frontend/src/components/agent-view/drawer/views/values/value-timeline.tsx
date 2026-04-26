import { ValueDetail } from "@/components/agent-view/drawer/views/values/value-detail";
import {
  type ValueTimelineRow,
  ValueRow,
} from "@/components/agent-view/drawer/views/values/value-row";
import { ValueDistributionSummary } from "@/components/agent-view/drawer/views/values/value-distribution-summary";
import { EmptyState } from "@/components/ui/empty-state";
import { useAgentValues } from "@/hooks/use-runs";
import type { AgentEventEnvelope, EventEnvelope } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useEventBufferStore, useUIStore } from "@/stores";
import type { DrawerPayload } from "@/stores/ui";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState } from "react";
import { z } from "zod";

const DrawerPayloadSchema = z.object({
  agentPath: z.string(),
  attr: z.string(),
  side: z.enum(["in", "out"]).default("in"),
});

const EMPTY_EVENTS: EventEnvelope[] = [];

type SortMode = "time" | "frequency" | "length";

type SimilarityFilter =
  | { kind: "string"; needle: string }
  | { kind: "number"; min: number; max: number }
  | null;

interface EnrichedRow extends ValueTimelineRow {
  signature: string;
  frequency: number;
  length: number;
}

interface ValueTimelineProps {
  payload: DrawerPayload;
  runId: string;
}

export function ValueTimeline({ payload, runId }: ValueTimelineProps) {
  const parsed = DrawerPayloadSchema.safeParse(payload);
  const openDrawer = useUIStore((s) => s.openDrawer);
  const setSelectedInvocation = useUIStore((s) => s.setSelectedInvocation);
  const selectedInvocationId = useUIStore((s) => s.selectedInvocationId);
  const selectedInvocationAgentPath = useUIStore((s) => s.selectedInvocationAgentPath);
  const agentPath = parsed.success ? parsed.data.agentPath : "";
  const attr = parsed.success ? parsed.data.attr : "";
  const initialSide = parsed.success ? parsed.data.side : "in";
  const parsedSide = parsed.success ? parsed.data.side : null;

  const [side, setSide] = useState<"in" | "out">(initialSide);
  const [sortMode, setSortMode] = useState<SortMode>("time");
  const [search, setSearch] = useState("");
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [similarityFilter, setSimilarityFilter] = useState<SimilarityFilter>(null);
  const [diffIds, setDiffIds] = useState<string[]>([]);
  const [nowSec, setNowSec] = useState(() => Date.now() / 1000);

  useEffect(() => {
    if (parsedSide) setSide(parsedSide);
  }, [parsedSide]);

  useEffect(() => {
    const id = window.setInterval(() => setNowSec(Date.now() / 1000), 5_000);
    return () => window.clearInterval(id);
  }, []);

  const valuesQuery = useAgentValues(runId, agentPath, attr, side);
  const runEvents = useEventBufferStore((s) => s.eventsByRun.get(runId) ?? EMPTY_EVENTS);

  const apiRows = useMemo(() => {
    const values = valuesQuery.data?.values ?? [];
    return values.map((entry) => ({
      invocationId: entry.invocation_id,
      startedAt: entry.started_at,
      value: entry.value,
    }));
  }, [valuesQuery.data]);

  const liveRows = useMemo(() => {
    return extractLiveRows(runEvents, agentPath, attr, side);
  }, [runEvents, agentPath, attr, side]);

  const merged = useMemo(() => {
    const rowsById = new Map<string, { invocationId: string; startedAt: number; value: unknown }>();
    for (const row of [...liveRows, ...apiRows]) {
      if (!rowsById.has(row.invocationId)) rowsById.set(row.invocationId, row);
    }
    return [...rowsById.values()];
  }, [apiRows, liveRows]);

  const rows = useMemo(() => {
    const signatures = merged.map((row) => stringifySafe(row.value));
    const frequencyMap = new Map<string, number>();
    for (const signature of signatures) {
      frequencyMap.set(signature, (frequencyMap.get(signature) ?? 0) + 1);
    }

    const numericValues = merged
      .map((row) => (typeof row.value === "number" && Number.isFinite(row.value) ? row.value : null))
      .filter((value): value is number => value != null);
    const mean =
      numericValues.length > 0
        ? numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length
        : 0;
    const variance =
      numericValues.length > 1
        ? numericValues.reduce((sum, value) => sum + (value - mean) ** 2, 0) / numericValues.length
        : 0;
    const stddev = Math.sqrt(variance);

    const enriched: EnrichedRow[] = merged.map((row) => {
      const signature = stringifySafe(row.value);
      const preview = previewValue(row.value);
      const length = signature.length;
      const frequency = frequencyMap.get(signature) ?? 1;
      let isOutlier = false;
      if (typeof row.value === "number" && stddev > 0) {
        const zScore = Math.abs((row.value - mean) / stddev);
        isOutlier = zScore > 2;
      } else {
        isOutlier = frequency / Math.max(1, merged.length) < 0.05;
      }
      const tokenEstimate =
        typeof row.value === "string" ? Math.round((wordCount(row.value) || 1) / 0.75) : null;
      return {
        invocationId: row.invocationId,
        startedAt: row.startedAt,
        value: row.value,
        preview,
        signature,
        frequency,
        length,
        isOutlier,
        tokenEstimate,
        repeated: false,
      };
    });

    const filteredSearch = enriched.filter((row) => {
      if (search && !row.preview.toLowerCase().includes(search.toLowerCase())) return false;
      if (!similarityFilter) return true;
      if (similarityFilter.kind === "string") {
        const asString = typeof row.value === "string" ? row.value : row.preview;
        return asString.toLowerCase().includes(similarityFilter.needle.toLowerCase());
      }
      if (typeof row.value !== "number" || !Number.isFinite(row.value)) return false;
      return row.value >= similarityFilter.min && row.value <= similarityFilter.max;
    });

    filteredSearch.sort((a, b) => {
      if (sortMode === "time") return b.startedAt - a.startedAt;
      if (sortMode === "frequency") {
        if (a.frequency !== b.frequency) return b.frequency - a.frequency;
        return b.startedAt - a.startedAt;
      }
      if (a.length !== b.length) return b.length - a.length;
      return b.startedAt - a.startedAt;
    });

    return filteredSearch.map((row, index, list) => ({
      ...row,
      repeated: index > 0 && list[index - 1]?.signature === row.signature,
    }));
  }, [merged, search, similarityFilter, sortMode]);

  useEffect(() => {
    if (rows.length === 0) {
      setSelectedRowId(null);
      return;
    }
    if (!selectedRowId || !rows.some((row) => row.invocationId === selectedRowId)) {
      setSelectedRowId(rows[0]?.invocationId ?? null);
    }
  }, [rows, selectedRowId]);

  const selectedRow = rows.find((row) => row.invocationId === selectedRowId) ?? null;

  const diffRows = useMemo(() => {
    if (diffIds.length !== 2) return [];
    const left = rows.find((row) => row.invocationId === diffIds[0]);
    const right = rows.find((row) => row.invocationId === diffIds[1]);
    if (!left || !right) return [];
    return structuralDiff(left.value, right.value);
  }, [rows, diffIds]);

  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 58,
    overscan: 10,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();
  const rowsToRender =
    virtualRows.length > 0
      ? virtualRows
      : rows.map((_, index) => ({ index, key: index, start: index * 58, size: 58 }));

  if (valuesQuery.isLoading) {
    return <div className="p-3 text-xs text-muted">loading values…</div>;
  }

  if (!parsed.success) {
    return (
      <div className="p-3">
        <EmptyState title="invalid values payload" description="missing agentPath/attr" />
      </div>
    );
  }

  if (valuesQuery.isError) {
    return <div className="p-3 text-xs text-err">failed to load values</div>;
  }

  const values = rows.map((row) => row.value);

  return (
    <div className="flex h-full flex-col gap-2 overflow-hidden p-2">
      <ValueDistributionSummary
        label={attr}
        values={values}
        side={side}
        typeName={valuesQuery.data?.type ?? "unknown"}
      />

      <div className="flex flex-wrap items-center gap-1 rounded border border-border bg-bg-1 px-2 py-1">
        <button
          type="button"
          className={cn(
            "rounded px-1.5 py-0.5 text-[11px]",
            side === "in" ? "bg-accent text-bg-0" : "bg-bg-2 text-muted",
          )}
          onClick={() => setSide("in")}
        >
          input
        </button>
        <button
          type="button"
          className={cn(
            "rounded px-1.5 py-0.5 text-[11px]",
            side === "out" ? "bg-accent text-bg-0" : "bg-bg-2 text-muted",
          )}
          onClick={() => setSide("out")}
        >
          output
        </button>

        <input
          className="ml-2 flex-1 rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-text"
          placeholder="search values"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <select
          aria-label="sort values"
          className="rounded border border-border bg-bg-2 px-1 py-1 text-[11px] text-text"
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value as SortMode)}
        >
          <option value="time">time</option>
          <option value="frequency">frequency</option>
          <option value="length">length</option>
        </select>

        <button
          type="button"
          className="rounded border border-border bg-bg-2 px-1.5 py-1 text-[11px] text-muted hover:text-text disabled:opacity-50"
          disabled={diffIds.length !== 2}
          onClick={() => {
            if (diffIds.length !== 2) return;
            const left = rows.find((row) => row.invocationId === diffIds[0]);
            if (left) setSelectedRowId(left.invocationId);
          }}
        >
          diff ({diffIds.length}/2)
        </button>
        {similarityFilter ? (
          <button
            type="button"
            className="rounded border border-border bg-bg-2 px-1.5 py-1 text-[11px] text-muted hover:text-text"
            onClick={() => setSimilarityFilter(null)}
          >
            clear similar
          </button>
        ) : null}
      </div>

      {rows.length === 0 ? (
        <div className="rounded border border-border bg-bg-1 p-3">
          <EmptyState title="no invocations yet for this attribute" />
        </div>
      ) : (
        <>
          <div ref={parentRef} className="min-h-0 flex-1 overflow-auto rounded border border-border bg-bg-1">
            <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: "relative" }}>
              {rowsToRender.map((virtual) => {
                const row = rows[virtual.index];
                if (!row) return null;
                return (
                  <div
                    key={row.invocationId}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: `${virtual.size}px`,
                      transform: `translateY(${virtual.start}px)`,
                    }}
                  >
                    <ValueRow
                      row={row}
                      nowSec={nowSec}
                      selected={selectedRow?.invocationId === row.invocationId}
                      selectedInvocation={
                        selectedInvocationId === row.invocationId &&
                        selectedInvocationAgentPath === agentPath
                      }
                      checkedForDiff={diffIds.includes(row.invocationId)}
                      onToggleDiff={(invocationId) => {
                        setDiffIds((prev) => {
                          if (prev.includes(invocationId)) {
                            return prev.filter((id) => id !== invocationId);
                          }
                          if (prev.length >= 2) return [prev[1] as string, invocationId];
                          return [...prev, invocationId];
                        });
                      }}
                      onSelect={() => setSelectedRowId(row.invocationId)}
                      onOpenInvocation={() => {
                        setSelectedInvocation(row.invocationId, agentPath);
                        openDrawer("events", { agentPath, invocationId: row.invocationId });
                      }}
                      onFindSimilar={() => {
                        if (typeof row.value === "string") {
                          setSimilarityFilter({ kind: "string", needle: row.value.slice(0, 50) });
                          return;
                        }
                        if (typeof row.value === "number" && Number.isFinite(row.value)) {
                          const span = Math.abs(row.value) * 0.1;
                          setSimilarityFilter({
                            kind: "number",
                            min: row.value - span,
                            max: row.value + span,
                          });
                        }
                      }}
                      onCopy={async () => {
                        try {
                          await navigator.clipboard.writeText(stringifySafe(row.value));
                        } catch {
                          // noop
                        }
                      }}
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {selectedRow ? <ValueDetail value={selectedRow.value} /> : null}

          {diffIds.length === 2 ? (
            <div className="rounded border border-border bg-bg-1 p-2">
              <div className="mb-1 text-[11px] uppercase tracking-[0.08em] text-muted">structural diff</div>
              {diffRows.length === 0 ? (
                <div className="text-[11px] text-muted">no structural changes</div>
              ) : (
                <div className="max-h-40 overflow-auto">
                  {diffRows.map((row) => (
                    <div
                      key={row.path}
                      className="grid grid-cols-[1fr_1fr_1fr] gap-2 border-b border-border/50 py-1 text-[11px]"
                    >
                      <span className="font-mono text-muted">{row.path || "(root)"}</span>
                      <span className="font-mono text-err">{stringifySafe(row.left)}</span>
                      <span className="font-mono text-ok">{stringifySafe(row.right)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function extractLiveRows(
  events: EventEnvelope[],
  agentPath: string,
  attr: string,
  side: "in" | "out",
): Array<{ invocationId: string; startedAt: number; value: unknown }> {
  const terminal = events
    .filter(
      (event): event is AgentEventEnvelope =>
        event.type === "agent_event" &&
        event.agent_path === agentPath &&
        (event.kind === "end" || event.kind === "error"),
    )
    .sort((a, b) => a.started_at - b.started_at);

  const out: Array<{ invocationId: string; startedAt: number; value: unknown }> = [];
  for (let index = 0; index < terminal.length; index++) {
    const event = terminal[index];
    if (!event) continue;
    const source = side === "in" ? event.input : extractOutputResponse(event);
    const [ok, value] = extractAttribute(source, attr);
    if (!ok) continue;
    out.push({ invocationId: `${agentPath}:${index}`, startedAt: event.started_at, value });
  }
  return out;
}

function extractOutputResponse(event: AgentEventEnvelope): unknown {
  if (!event.output || typeof event.output !== "object") return null;
  const output = event.output as Record<string, unknown>;
  const response = output.response;
  if (response && typeof response === "object") return response;
  return output;
}

function extractAttribute(value: unknown, attr: string): [boolean, unknown] {
  const parts = attr.split(".");
  let current: unknown = value;
  for (const part of parts) {
    if (!current || typeof current !== "object") return [false, null];
    const record = current as Record<string, unknown>;
    if (!(part in record)) return [false, null];
    current = record[part];
  }
  return [true, current];
}

function previewValue(value: unknown): string {
  if (typeof value === "string") return truncate(value.replace(/\s+/g, " "), 120);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value == null) return String(value);
  if (Array.isArray(value)) {
    const head = value.slice(0, 3).map((item) => stringifySafe(item));
    return `[${value.length}] ${truncate(head.join(", "), 120)}`;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record);
    return `{${keys.slice(0, 4).join(", ")}${keys.length > 4 ? ", …" : ""}}`;
  }
  return truncate(String(value), 120);
}

function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

function stringifySafe(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function wordCount(text: string): number {
  const words = text.trim().split(/\s+/).filter((token) => token.length > 0);
  return words.length;
}

interface DiffRow {
  path: string;
  left: unknown;
  right: unknown;
}

function structuralDiff(left: unknown, right: unknown, prefix = ""): DiffRow[] {
  if (Object.is(left, right)) return [];

  if (
    left == null ||
    right == null ||
    typeof left !== "object" ||
    typeof right !== "object" ||
    Array.isArray(left) !== Array.isArray(right)
  ) {
    return [{ path: prefix, left, right }];
  }

  const leftRecord = left as Record<string, unknown>;
  const rightRecord = right as Record<string, unknown>;
  const keys = new Set([...Object.keys(leftRecord), ...Object.keys(rightRecord)]);
  const out: DiffRow[] = [];
  for (const key of keys) {
    const path = prefix ? `${prefix}.${key}` : key;
    out.push(...structuralDiff(leftRecord[key], rightRecord[key], path));
  }
  return out;
}
