/**
 * Convert a JsonlObserver record (event: "agent"|"algorithm") to an
 * SSE Envelope (type: "agent_event"|"algo_event"). Mirrors
 * apps/dashboard/operad_dashboard/replay.py:record_to_envelope so
 * trace fixtures and dashboard --replay agree on the conversion.
 */
import type { Envelope } from "@/lib/types";

interface JsonlAgentRecord {
  event: "agent";
  run_id: string;
  agent_path: string;
  kind: string;
  input?: unknown;
  output?: unknown;
  started_at: number;
  finished_at: number | null;
  metadata?: Record<string, unknown>;
  error?: { type: string; message: string } | null;
}

interface JsonlAlgoRecord {
  event: "algorithm";
  run_id: string;
  algorithm_path: string;
  kind: string;
  payload?: Record<string, unknown>;
  started_at: number;
  finished_at: number | null;
  metadata?: Record<string, unknown>;
}

export type JsonlRecord = JsonlAgentRecord | JsonlAlgoRecord;

export function jsonlRecordToEnvelope(rec: JsonlRecord): Envelope | null {
  if (rec.event === "agent") {
    return {
      type: "agent_event",
      run_id: rec.run_id,
      agent_path: rec.agent_path,
      kind: rec.kind as "start" | "end" | "error" | "chunk",
      input: rec.input ?? null,
      output: rec.output ?? null,
      started_at: rec.started_at,
      finished_at: rec.finished_at,
      metadata: rec.metadata ?? {},
      error: rec.error ?? null,
    };
  }
  if (rec.event === "algorithm") {
    return {
      type: "algo_event",
      run_id: rec.run_id,
      algorithm_path: rec.algorithm_path,
      kind: rec.kind,
      payload: rec.payload ?? {},
      started_at: rec.started_at,
      finished_at: rec.finished_at,
      metadata: rec.metadata ?? {},
    };
  }
  return null;
}

export function parseJsonl(text: string): JsonlRecord[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .map((s) => JSON.parse(s) as JsonlRecord);
}
