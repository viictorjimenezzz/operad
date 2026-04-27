import { Badge } from "@/components/ui/badge";
import type { EventEnvelope } from "@/lib/types";
import { cn, formatDurationMs, truncateMiddle } from "@/lib/utils";
import type { CSSProperties, ReactNode } from "react";

interface EventRowProps {
  event: EventEnvelope;
  index: number;
  active: boolean;
  selected: boolean;
  style?: CSSProperties;
  onSelect: (index: number) => void;
}

type Summarizer = (event: EventEnvelope) => ReactNode;

const SUMMARIZERS: Record<string, Summarizer> = {
  algo_start: (event) => `${pretty(eventPath(event))} ${pluck(event, "n", "max_iter", "rounds")}`,
  generation: (event) => {
    const payload = eventPayload(event);
    return `gen ${fmtValue(payload.gen_index)}: best ${fmt(payload.best)}`;
  },
  candidate: (event) => {
    const payload = eventPayload(event);
    return `cand #${fmtValue(payload.candidate_index)} score ${fmt(payload.score)}`;
  },
  cell: (event) => {
    const payload = eventPayload(event);
    return `cell #${fmtValue(payload.cell_index)} ${shortParams(payload.parameters)}`;
  },
  round: (event) => {
    const payload = eventPayload(event);
    return `round ${fmtValue(payload.round_index)} mean ${fmt(mean(payload.scores))}`;
  },
  iteration: (event) => {
    const payload = eventPayload(event);
    return `iter ${fmtValue(payload.iter_index)} ${fmtValue(payload.phase)} ${fmt(payload.score)}`;
  },
  gradient_applied: (event) => {
    const payload = eventPayload(event);
    return `severity ${fmt(payload.severity)} -> ${joinValues(payload.target_paths)}`;
  },
  batch_end: (event) => {
    const payload = eventPayload(event);
    return `epoch ${fmtValue(payload.epoch)} batch ${fmtValue(payload.batch ?? payload.batch_index)} loss ${fmt(payload.train_loss)}`;
  },
  start: (event) => `${pretty(eventPath(event))} start`,
  end: (event) => `${pretty(eventPath(event))} end (${formatDurationMs(eventLatencyMs(event))})`,
  error: (event) => {
    if (event.type !== "agent_event") return "error";
    return `${pretty(event.agent_path)} error ${event.error?.message ?? ""}`.trim();
  },
  algo_error: (event) => {
    const payload = eventPayload(event);
    return `error ${fmtValue(payload.message)}`;
  },
};

export function EventRow({ event, index, active, selected, style, onSelect }: EventRowProps) {
  const isError =
    (event.type === "agent_event" && event.kind === "error") || event.kind === "algo_error";

  return (
    <button
      type="button"
      style={style}
      onClick={() => onSelect(index)}
      className={cn(
        "absolute left-0 top-0 grid w-full grid-cols-[96px_92px_minmax(120px,0.7fr)_112px_minmax(0,1fr)] items-center gap-2 border-b border-border/70 px-2 py-1.5 text-left text-[11px] leading-5 transition-colors hover:bg-bg-2",
        active && "bg-bg-2/70",
        selected && "outline outline-1 outline-[--color-accent-dim]",
      )}
      aria-current={selected ? "true" : undefined}
    >
      <span className="font-mono tabular-nums text-muted">{formatTimestamp(event.started_at)}</span>
      <span className="min-w-0">
        <Badge variant={isError ? "error" : event.type === "algo_event" ? "algo" : "default"}>
          {event.type}
        </Badge>
      </span>
      <span className="truncate font-mono text-muted" title={eventPath(event)}>
        {truncateMiddle(eventPath(event), 34)}
      </span>
      <span className="truncate font-mono text-text" title={event.kind}>
        {event.kind}
      </span>
      <span className="truncate text-muted" title={String(eventSummary(event))}>
        {eventSummary(event)}
      </span>
    </button>
  );
}

export function eventSummary(event: EventEnvelope): ReactNode {
  const summarizer = SUMMARIZERS[event.kind];
  if (summarizer) return summarizer(event);
  return `${event.kind} (payload omitted)`;
}

export function eventPath(event: EventEnvelope): string {
  return event.type === "agent_event" ? event.agent_path : event.algorithm_path;
}

export function eventPayload(event: EventEnvelope): Record<string, unknown> {
  return event.type === "algo_event" ? event.payload : {};
}

export function eventSeverityBucket(event: EventEnvelope): "low" | "medium" | "high" | null {
  if (event.kind !== "gradient_applied") return null;
  const severity = eventPayload(event).severity;
  if (typeof severity !== "number" || !Number.isFinite(severity)) return null;
  if (severity < 0.34) return "low";
  if (severity < 0.67) return "medium";
  return "high";
}

export function spanIdFromMetadata(metadata: Record<string, unknown>): string | null {
  const value = metadata.span_id ?? metadata.spanId ?? metadata.observation_id;
  return typeof value === "string" && value.length > 0 ? value : null;
}

function eventLatencyMs(event: EventEnvelope): number | null {
  const metadataLatency = event.metadata.latency_ms;
  if (typeof metadataLatency === "number" && Number.isFinite(metadataLatency))
    return metadataLatency;
  const finished = event.finished_at ?? event.started_at;
  return Math.max(0, (finished - event.started_at) * 1000);
}

function formatTimestamp(seconds: number): string {
  const date = new Date(seconds * 1000);
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  const ms = String(date.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

function pluck(event: EventEnvelope, ...keys: string[]): string {
  const payload = eventPayload(event);
  const parts = keys.flatMap((key) => {
    const value = payload[key];
    return value == null ? [] : [`${key}=${String(value)}`];
  });
  return parts.join(" ");
}

function shortParams(value: unknown): string {
  if (!isRecord(value)) return "";
  return Object.entries(value)
    .slice(0, 3)
    .map(([key, item]) => `${key}=${String(item)}`)
    .join(", ");
}

function fmt(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return value.toFixed(3);
  if (value == null) return "-";
  return String(value);
}

function fmtValue(value: unknown): string {
  if (value == null || value === "") return "-";
  return String(value);
}

function mean(value: unknown): number | null {
  if (!Array.isArray(value)) return null;
  const nums = value.filter((item): item is number => typeof item === "number");
  if (nums.length === 0) return null;
  return nums.reduce((sum, item) => sum + item, 0) / nums.length;
}

function joinValues(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join(", ");
  return value == null ? "-" : String(value);
}

function pretty(path: string): string {
  return path.split(".").filter(Boolean).at(-1) ?? path;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
