import { SSEDispatcher, type StreamStatus } from "@/components/runtime/sse-dispatcher";
import { Envelope } from "@/lib/types";
import { dispatchEnvelope, useStreamStore } from "@/stores";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import type { ZodTypeAny } from "zod";

/**
 * Open the dashboard's multiplexed /stream and route every envelope
 * through dispatchEnvelope() into the right Zustand slice. On reconnect
 * we invalidate ["runs"] so the UI repairs the gap (the multiplex
 * stream itself does not replay history).
 */
export function useDashboardStream(url = "/stream"): StreamStatus {
  const status = useStreamStore((s) => s.status);
  const setStatus = useStreamStore((s) => s.setStatus);
  const queryClient = useQueryClient();
  const dispatcherRef = useRef<SSEDispatcher | null>(null);

  useEffect(() => {
    const d = new SSEDispatcher({
      url,
      schema: Envelope,
      onMessage: (env) => dispatchEnvelope(env as Envelope),
      onStatus: (s) => {
        setStatus(s);
        if (s === "reconnecting" || s === "live") {
          queryClient.invalidateQueries({ queryKey: ["runs"] });
        }
      },
      onUnknown: (raw, error) => {
        console.warn("operad: unparseable SSE envelope", raw, error);
      },
    });
    d.open();
    dispatcherRef.current = d;
    return () => {
      d.close();
      dispatcherRef.current = null;
    };
  }, [url, setStatus, queryClient]);

  return status;
}

/**
 * Open a per-panel SSE endpoint and call `onSnapshot` on every parsed
 * payload. Used by panels whose `.sse` URL ships a derived shape, not
 * the raw envelope (fitness.sse, mutations.sse, drift.sse, progress.sse).
 */
export function usePanelStream<T>(
  url: string | null,
  schema: ZodTypeAny,
  onSnapshot: (parsed: T) => void,
): void {
  const onSnapshotRef = useRef(onSnapshot);
  onSnapshotRef.current = onSnapshot;

  useEffect(() => {
    if (!url) return;
    const d = new SSEDispatcher<T>({
      url,
      schema,
      onMessage: (parsed) => onSnapshotRef.current(parsed),
    });
    d.open();
    return () => d.close();
  }, [url, schema]);
}
