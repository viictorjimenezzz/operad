export { useUIStore } from "@/stores/ui";
export type {
  EventKindFilter,
  GraphSelection,
  GraphInspectorTab,
} from "@/stores/ui";
export { useRunStore } from "@/stores/run";
export { useEventBufferStore, eventBufferLimits } from "@/stores/eventBuffer";
export { useStatsStore } from "@/stores/stats";
export { useStreamStore } from "@/stores/stream";

import type { Envelope } from "@/lib/types";
import { useEventBufferStore } from "@/stores/eventBuffer";
import { useStatsStore } from "@/stores/stats";

/**
 * Single dispatch entry-point used by useDashboardStream() (PR3) to
 * route a parsed envelope into the right Zustand slice.
 */
export function dispatchEnvelope(envelope: Envelope): void {
  switch (envelope.type) {
    case "agent_event":
    case "algo_event":
      useEventBufferStore.getState().ingest(envelope);
      break;
    case "slot_occupancy":
      useStatsStore.getState().setSlots(envelope.snapshot);
      break;
    case "cost_update":
      useStatsStore.getState().setCosts(envelope.totals);
      break;
    case "stats_update":
      useStatsStore.getState().setGlobal(envelope.stats);
      break;
  }
}
