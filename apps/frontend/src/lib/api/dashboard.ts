import {
  DriftEntry,
  EvolutionResponse,
  ArchivedRunRecord,
  FitnessEntry,
  GraphResponse,
  Manifest,
  MutationsMatrix,
  ProgressSnapshot,
  RunEventsResponse,
  RunSummary,
  StatsResponse,
} from "@/lib/types";
/**
 * Typed fetch wrappers for the dashboard FastAPI. Every response is
 * Zod-validated so the rest of the app deals with parsed shapes only.
 *
 * The base URL is empty in production (same-origin). In dev, Vite's
 * proxy (vite.config.ts) forwards /runs, /graph, /stream, etc. to the
 * Python backend on :7860.
 */
import { z } from "zod";

async function getJson<T extends z.ZodTypeAny>(url: string, schema: T): Promise<z.infer<T>> {
  const r = await fetch(url, { headers: { accept: "application/json" } });
  if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← ${url}`);
  const raw: unknown = await r.json();
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    throw new ParseError(url, parsed.error);
  }
  return parsed.data;
}

export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "HttpError";
  }
}

export class ParseError extends Error {
  constructor(
    public url: string,
    public zodError: z.ZodError,
  ) {
    super(`response from ${url} did not match schema: ${zodError.message}`);
    this.name = "ParseError";
  }
}

export const dashboardApi = {
  runs: () => getJson("/runs", z.array(RunSummary)),
  runsWithParams: (params: { includeSynthetic?: boolean }) => {
    const qs = params.includeSynthetic ? "?include=synthetic" : "";
    return getJson(`/runs${qs}`, z.array(RunSummary));
  },
  runChildren: (runId: string) => getJson(`/runs/${runId}/children`, z.array(RunSummary)),
  runSummary: (runId: string) => getJson(`/runs/${runId}/summary`, RunSummary),
  runEvents: (runId: string, limit = 500) =>
    getJson(`/runs/${runId}/events?limit=${limit}`, RunEventsResponse),
  graph: (runId: string) => getJson(`/graph/${runId}`, GraphResponse),
  fitness: (runId: string) => getJson(`/runs/${runId}/fitness.json`, z.array(FitnessEntry)),
  mutations: (runId: string) => getJson(`/runs/${runId}/mutations.json`, MutationsMatrix),
  drift: (runId: string) => getJson(`/runs/${runId}/drift.json`, z.array(DriftEntry)),
  progress: (runId: string) => getJson(`/runs/${runId}/progress.json`, ProgressSnapshot),
  stats: () => getJson("/stats", StatsResponse),
  evolution: () => getJson("/evolution", EvolutionResponse),
  manifest: () => getJson("/api/manifest", Manifest),
  archive: (params: { from?: number; to?: number; algorithm?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params.from != null) qs.set("from", String(params.from));
    if (params.to != null) qs.set("to", String(params.to));
    if (params.algorithm) qs.set("algorithm", params.algorithm);
    if (params.limit != null) qs.set("limit", String(params.limit));
    const suffix = qs.size > 0 ? `?${qs.toString()}` : "";
    return getJson(`/archive${suffix}`, z.array(RunSummary));
  },
  archivedRun: (runId: string) => getJson(`/archive/${runId}`, ArchivedRunRecord),
  restoreArchivedRun: async (runId: string) => {
    const url = `/archive/${runId}/restore`;
    const r = await fetch(url, { method: "POST", headers: { accept: "application/json" } });
    if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← ${url}`);
    const raw: unknown = await r.json();
    const parsed = z.object({ ok: z.boolean(), run: RunSummary }).safeParse(raw);
    if (!parsed.success) throw new ParseError(url, parsed.error);
    return parsed.data;
  },
  deleteArchivedRun: async (runId: string) => {
    const r = await fetch(`/archive/${runId}`, { method: "DELETE" });
    if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← /archive/${runId}`);
    const raw: unknown = await r.json();
    const parsed = z.object({ ok: z.boolean() }).safeParse(raw);
    if (!parsed.success) throw new ParseError(`/archive/${runId}`, parsed.error);
    return parsed.data;
  },
  exportArchiveJsonl: async () => {
    const r = await fetch("/archive/_export?format=jsonl", {
      method: "POST",
      headers: { accept: "application/x-ndjson" },
    });
    if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← /archive/_export?format=jsonl`);
    return r.text();
  },
} as const;
