import { Card, CardContent } from "@/components/ui/card";
import { useAgentEvents } from "@/hooks/use-runs";
import type { AgentEventEnvelope, Envelope, RunInvocation } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useEventBufferStore } from "@/stores";
import { useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";

type ReplaySpeed = "0.5x" | "1x" | "2x" | "fast";

interface ReplayChunk {
  signature: string;
  startedAt: number;
  chunkIndex: number | null;
  text: string;
  invocationId: string | null;
}

interface ReplayInvocation {
  invocationId: string;
  input: unknown;
  hashContent: string | null;
  chunks: ReplayChunk[];
}

interface ChunkReplayProps {
  runId: string;
  agentPath: string;
  invocations: RunInvocation[];
}

const EMPTY_EVENTS: Envelope[] = [];
const SPEED_MULTIPLIER: Record<Exclude<ReplaySpeed, "fast">, number> = {
  "0.5x": 0.5,
  "1x": 1,
  "2x": 2,
};

export function ChunkReplay({ runId, agentPath, invocations }: ChunkReplayProps) {
  const liveRunEvents = useEventBufferStore((s) => s.eventsByRun.get(runId) ?? EMPTY_EVENTS);
  const archived = useAgentEvents(runId, agentPath, 1_000);
  const replayInvocations = useMemo(
    () =>
      buildReplayInvocations({
        runId,
        agentPath,
        invocations,
        archivedEvents: archived.data?.events ?? [],
        liveEvents: liveRunEvents,
      }),
    [agentPath, archived.data?.events, invocations, liveRunEvents, runId],
  );

  const [selectedInvocationId, setSelectedInvocationId] = useState<string | null>(null);
  const [visibleChunkCount, setVisibleChunkCount] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState<ReplaySpeed>("1x");
  const timersRef = useRef<number[]>([]);

  useEffect(() => {
    if (replayInvocations.length === 0) {
      setSelectedInvocationId(null);
      setVisibleChunkCount(0);
      setIsPlaying(false);
      clearTimers(timersRef);
      return;
    }
    setSelectedInvocationId((prev) =>
      prev && replayInvocations.some((inv) => inv.invocationId === prev)
        ? prev
        : replayInvocations[0]?.invocationId ?? null,
    );
  }, [replayInvocations]);

  const selected = useMemo(
    () =>
      replayInvocations.find((inv) => inv.invocationId === selectedInvocationId) ?? null,
    [replayInvocations, selectedInvocationId],
  );

  useEffect(() => {
    setVisibleChunkCount(0);
    setIsPlaying(false);
    clearTimers(timersRef);
  }, [selectedInvocationId]);

  useEffect(
    () => () => {
      clearTimers(timersRef);
    },
    [],
  );

  if (replayInvocations.length === 0) return null;
  if (!selected) return null;

  const totalChunks = selected.chunks.length;
  const playbackText = selected.chunks
    .slice(0, visibleChunkCount)
    .map((chunk) => chunk.text)
    .join("");
  const ticksId = `chunk-replay-${runId}-${agentPath}-${selected.invocationId}`
    .replaceAll(".", "-")
    .replaceAll(":", "-");

  const play = () => {
    if (totalChunks === 0 || visibleChunkCount >= totalChunks) return;
    clearTimers(timersRef);
    if (speed === "fast") {
      setVisibleChunkCount(totalChunks);
      setIsPlaying(false);
      return;
    }
    const speedFactor = SPEED_MULTIPLIER[speed];
    const startAt = selected.chunks[visibleChunkCount]?.startedAt ?? selected.chunks[0]?.startedAt;
    if (startAt == null) return;
    setIsPlaying(true);
    for (let idx = visibleChunkCount; idx < totalChunks; idx += 1) {
      const chunk = selected.chunks[idx];
      if (!chunk) continue;
      const delayMs = ((chunk.startedAt - startAt) * 1000) / speedFactor;
      const timeoutId = window.setTimeout(() => {
        setVisibleChunkCount(Math.max(0, idx + 1));
        if (idx === totalChunks - 1) {
          setIsPlaying(false);
        }
      }, Math.max(0, delayMs));
      timersRef.current.push(timeoutId);
    }
  };

  const pause = () => {
    clearTimers(timersRef);
    setIsPlaying(false);
  };

  const reset = () => {
    clearTimers(timersRef);
    setIsPlaying(false);
    setVisibleChunkCount(0);
  };

  return (
    <Card>
      <CardContent className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[0.72rem] font-semibold uppercase tracking-[0.08em] text-muted">
            replay
          </div>
          {replayInvocations.length > 1 ? (
            <label className="flex items-center gap-1 text-[11px] text-muted">
              invocation
              <select
                value={selected.invocationId}
                onChange={(e) => setSelectedInvocationId(e.target.value)}
                className="rounded border border-border bg-bg-2 px-1.5 py-1 font-mono text-[11px] text-text"
              >
                {replayInvocations.map((inv, index) => (
                  <option key={inv.invocationId} value={inv.invocationId}>
                    #{index + 1}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-1">
          <button
            type="button"
            className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-text"
            onClick={isPlaying ? pause : play}
          >
            {isPlaying ? "pause" : "play"}
          </button>
          <button
            type="button"
            className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-text"
            onClick={reset}
          >
            reset
          </button>
          <select
            aria-label="replay speed"
            value={speed}
            onChange={(e) => setSpeed(e.target.value as ReplaySpeed)}
            className="rounded border border-border bg-bg-2 px-1.5 py-1 text-[11px] text-text"
          >
            <option value="0.5x">0.5x</option>
            <option value="1x">1x</option>
            <option value="2x">2x</option>
            <option value="fast">fast</option>
          </select>
          <span className="ml-auto text-[11px] text-muted">
            {visibleChunkCount}/{totalChunks}
          </span>
        </div>

        <div className="space-y-1">
          <input
            type="range"
            min={0}
            max={totalChunks}
            step={1}
            value={visibleChunkCount}
            list={ticksId}
            onChange={(e) => {
              clearTimers(timersRef);
              setIsPlaying(false);
              setVisibleChunkCount(Number(e.target.value));
            }}
            className="w-full"
          />
          <datalist id={ticksId}>
            {selected.chunks.map((_, idx) => (
              <option key={idx} value={idx + 1} />
            ))}
          </datalist>
        </div>

        <div className="rounded border border-border bg-bg-2 p-2">
          <pre className="m-0 whitespace-pre-wrap break-words font-mono text-[11px] text-text">
            {playbackText}
            <span
              className={cn(
                "ml-0.5 inline-block w-[6px] align-middle text-muted",
                isPlaying ? "animate-pulse" : "",
                visibleChunkCount >= totalChunks ? "opacity-0" : "opacity-100",
              )}
            >
              |
            </span>
          </pre>
        </div>

        <div className="grid gap-1 text-[11px] text-muted">
          <div>
            input:{" "}
            <code className="text-text">
              {formatInputPreview(selected.input)}
            </code>
          </div>
          <div>
            final hash:{" "}
            <code className="text-text">{selected.hashContent ?? "—"}</code>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function clearTimers(ref: MutableRefObject<number[]>): void {
  for (const id of ref.current) window.clearTimeout(id);
  ref.current = [];
}

function formatInputPreview(input: unknown): string {
  if (input == null) return "not captured";
  try {
    const text = JSON.stringify(input);
    return text.length <= 180 ? text : `${text.slice(0, 177)}...`;
  } catch {
    return String(input);
  }
}

function buildReplayInvocations({
  runId,
  agentPath,
  invocations,
  archivedEvents,
  liveEvents,
}: {
  runId: string;
  agentPath: string;
  invocations: RunInvocation[];
  archivedEvents: Envelope[];
  liveEvents: Envelope[];
}): ReplayInvocation[] {
  const chunks = mergeChunkEvents({ runId, agentPath, archivedEvents, liveEvents });
  if (chunks.length === 0) return [];

  const sortedInvocations = [...invocations].sort((a, b) => a.started_at - b.started_at);
  const byInvocation = new Map<string, ReplayChunk[]>();
  for (const inv of sortedInvocations) {
    byInvocation.set(inv.id, []);
  }

  for (const chunk of chunks) {
    const assigned = chunk.invocationId
      ? sortedInvocations.find((inv) => inv.id === chunk.invocationId) ?? null
      : findInvocationByTime(sortedInvocations, chunk.startedAt);
    if (!assigned) continue;
    const list = byInvocation.get(assigned.id);
    if (!list) continue;
    list.push({ ...chunk, invocationId: assigned.id });
  }

  return sortedInvocations
    .map((inv) => ({
      invocationId: inv.id,
      input: inv.input ?? null,
      hashContent: inv.hash_content ?? null,
      chunks: byInvocation.get(inv.id) ?? [],
    }))
    .filter((inv) => inv.chunks.length > 0);
}

function mergeChunkEvents({
  runId,
  agentPath,
  archivedEvents,
  liveEvents,
}: {
  runId: string;
  agentPath: string;
  archivedEvents: Envelope[];
  liveEvents: Envelope[];
}): ReplayChunk[] {
  const merged = [...archivedEvents, ...liveEvents];
  const dedup = new Map<string, ReplayChunk>();

  for (const event of merged) {
    if (!isChunkEvent(event, runId, agentPath)) continue;
    const text = textFromChunkEvent(event);
    const chunkIndex = chunkIndexFromMetadata(event.metadata);
    const invocationId = invocationIdFromMetadata(event.metadata);
    const signature = [
      event.run_id,
      event.agent_path,
      event.started_at,
      chunkIndex ?? "na",
      text,
    ].join("|");
    if (!dedup.has(signature)) {
      dedup.set(signature, {
        signature,
        startedAt: event.started_at,
        chunkIndex,
        text,
        invocationId,
      });
    }
  }

  return [...dedup.values()].sort((a, b) =>
    a.startedAt === b.startedAt
      ? (a.chunkIndex ?? Number.MAX_SAFE_INTEGER) - (b.chunkIndex ?? Number.MAX_SAFE_INTEGER)
      : a.startedAt - b.startedAt,
  );
}

function isChunkEvent(
  event: Envelope,
  runId: string,
  agentPath: string,
): event is AgentEventEnvelope {
  return (
    event.type === "agent_event" &&
    event.run_id === runId &&
    event.agent_path === agentPath &&
    event.kind === "chunk"
  );
}

function textFromChunkEvent(event: AgentEventEnvelope): string {
  const raw = (event.metadata?.text ?? "") as unknown;
  if (typeof raw === "string") return raw;
  return "";
}

function chunkIndexFromMetadata(metadata: Record<string, unknown>): number | null {
  const index = metadata.chunk_index;
  return typeof index === "number" ? index : null;
}

function invocationIdFromMetadata(metadata: Record<string, unknown>): string | null {
  const value =
    metadata.invocation_id ??
    metadata.invocationId ??
    metadata.invocation ??
    metadata.call_id;
  return typeof value === "string" && value.length > 0 ? value : null;
}

function findInvocationByTime(
  invocations: RunInvocation[],
  startedAt: number,
): RunInvocation | null {
  let latestStart: RunInvocation | null = null;
  for (const invocation of invocations) {
    if (startedAt < invocation.started_at) break;
    latestStart = invocation;
    if (
      typeof invocation.finished_at === "number" &&
      startedAt <= invocation.finished_at
    ) {
      return invocation;
    }
  }
  return latestStart;
}

export { buildReplayInvocations, mergeChunkEvents };
