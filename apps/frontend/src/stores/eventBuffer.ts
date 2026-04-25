import type { Envelope, EventEnvelope, Generation } from "@/lib/types";
import { create } from "zustand";

const MAX_EVENTS_PER_RUN = 500;
const MAX_LIVE_GENERATIONS = 200;

interface EventBufferState {
  /** Per-run rolling buffer; mirrors the Python RunRegistry's deque cap. */
  eventsByRun: Map<string, EventEnvelope[]>;
  /** Cross-run rolling buffer of generation events for the global Evolution tab. */
  liveGenerations: Generation[];
  /** Last envelope we ingested (any kind), for the raw tab. */
  latestEnvelope: Envelope | null;
  ingest: (envelope: Envelope) => void;
  clear: (runId?: string) => void;
}

function isEventEnvelope(env: Envelope): env is EventEnvelope {
  return env.type === "agent_event" || env.type === "algo_event";
}

export const useEventBufferStore = create<EventBufferState>((set) => ({
  eventsByRun: new Map(),
  liveGenerations: [],
  latestEnvelope: null,
  ingest: (envelope) =>
    set((state) => {
      const next: Partial<EventBufferState> = { latestEnvelope: envelope };

      if (isEventEnvelope(envelope)) {
        const buf = state.eventsByRun.get(envelope.run_id) ?? [];
        const updated = [...buf, envelope];
        if (updated.length > MAX_EVENTS_PER_RUN) {
          updated.splice(0, updated.length - MAX_EVENTS_PER_RUN);
        }
        const map = new Map(state.eventsByRun);
        map.set(envelope.run_id, updated);
        next.eventsByRun = map;
      }

      if (envelope.type === "algo_event" && envelope.kind === "generation") {
        const payload = envelope.payload as Record<string, unknown>;
        const scores = (payload.population_scores as number[] | undefined) ?? [];
        const numericScores = scores.filter((s): s is number => typeof s === "number");
        const best = numericScores.length > 0 ? Math.max(...numericScores) : null;
        const mean =
          numericScores.length > 0
            ? numericScores.reduce((a, b) => a + b, 0) / numericScores.length
            : null;
        const generation: Generation = {
          gen_index: typeof payload.gen_index === "number" ? payload.gen_index : null,
          best,
          mean,
          scores: numericScores,
          survivor_indices: ((payload.survivor_indices as number[] | undefined) ?? []).filter(
            (n): n is number => typeof n === "number",
          ),
          op_attempt_counts:
            (payload.op_attempt_counts as Record<string, number> | undefined) ?? {},
          op_success_counts:
            (payload.op_success_counts as Record<string, number> | undefined) ?? {},
          timestamp: envelope.finished_at ?? envelope.started_at ?? null,
        };
        const generations = [...state.liveGenerations, generation];
        if (generations.length > MAX_LIVE_GENERATIONS) {
          generations.splice(0, generations.length - MAX_LIVE_GENERATIONS);
        }
        next.liveGenerations = generations;
      }

      return next as EventBufferState;
    }),
  clear: (runId) =>
    set((state) => {
      if (runId === undefined) {
        return { eventsByRun: new Map(), liveGenerations: [], latestEnvelope: null };
      }
      const map = new Map(state.eventsByRun);
      map.delete(runId);
      return { eventsByRun: map };
    }),
}));

export const eventBufferLimits = {
  maxEventsPerRun: MAX_EVENTS_PER_RUN,
  maxLiveGenerations: MAX_LIVE_GENERATIONS,
} as const;
