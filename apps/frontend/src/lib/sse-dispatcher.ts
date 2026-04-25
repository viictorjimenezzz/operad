/**
 * Typed wrapper around EventSource with reconnect/backoff. One instance
 * per <SSE URL>; the global dashboard stream and per-panel streams use
 * separate instances.
 *
 * On every `message` event we Zod-parse the payload and call
 * `onEnvelope` (for the multiplex /stream) or `onSnapshot` (for panel
 * .sse endpoints which ship derived shapes). Parse failures fall back
 * to `onUnknown` so an unexpected wire shape doesn't kill the stream.
 *
 * Reconnect: exponential backoff 250ms → 5s on `error`. Server-side,
 * the per-panel /runs/{id}/*.sse routes already replay history on
 * subscribe (per_run_sse in routes/__init__.py), so reconnect repairs
 * the per-panel gap. The multiplex /stream does NOT replay; the caller
 * (use-dashboard-stream.ts) refetches summary + events on reconnect.
 */
import type { ZodTypeAny, z } from "zod";

export type StreamStatus = "idle" | "connecting" | "live" | "reconnecting" | "error";

const MIN_BACKOFF_MS = 250;
const MAX_BACKOFF_MS = 5_000;

export interface DispatcherOptions<T> {
  url: string;
  schema: ZodTypeAny;
  onMessage: (parsed: T) => void;
  onUnknown?: (raw: unknown, error: unknown) => void;
  onStatus?: (status: StreamStatus) => void;
}

export class SSEDispatcher<T = unknown> {
  private url: string;
  private schema: ZodTypeAny;
  private onMessage: (parsed: T) => void;
  private onUnknown: (raw: unknown, error: unknown) => void;
  private onStatus: (status: StreamStatus) => void;
  private es: EventSource | null = null;
  private backoff = MIN_BACKOFF_MS;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;

  constructor(opts: DispatcherOptions<T>) {
    this.url = opts.url;
    this.schema = opts.schema;
    this.onMessage = opts.onMessage;
    this.onUnknown = opts.onUnknown ?? (() => {});
    this.onStatus = opts.onStatus ?? (() => {});
  }

  open(): void {
    if (this.closed) return;
    this.onStatus(this.es ? "reconnecting" : "connecting");
    const es = new EventSource(this.url);
    this.es = es;

    es.addEventListener("open", () => {
      this.backoff = MIN_BACKOFF_MS;
      this.onStatus("live");
    });

    es.addEventListener("message", (ev: MessageEvent<string>) => {
      let raw: unknown;
      try {
        raw = JSON.parse(ev.data);
      } catch (err) {
        this.onUnknown(ev.data, err);
        return;
      }
      const parsed = this.schema.safeParse(raw);
      if (parsed.success) {
        this.onMessage(parsed.data as T);
      } else {
        this.onUnknown(raw, parsed.error);
      }
    });

    es.addEventListener("error", () => {
      es.close();
      this.es = null;
      if (this.closed) return;
      this.onStatus("reconnecting");
      const delay = this.backoff;
      this.backoff = Math.min(MAX_BACKOFF_MS, this.backoff * 2);
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.open();
      }, delay);
    });
  }

  close(): void {
    this.closed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.es) {
      this.es.close();
      this.es = null;
    }
    this.onStatus("idle");
  }
}

/**
 * Convenience: parse one envelope from arbitrary JSON. Used by tests
 * and by the dashboard's reconnect refetch path.
 */
export function parseEnvelope<S extends ZodTypeAny>(
  raw: unknown,
  schema: S,
): { ok: true; data: z.infer<S> } | { ok: false; error: unknown } {
  const parsed = schema.safeParse(raw);
  return parsed.success ? { ok: true, data: parsed.data } : { ok: false, error: parsed.error };
}
