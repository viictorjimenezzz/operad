import {
  BenchmarkDetailResponse,
  BenchmarkIngestResponse,
  BenchmarkListItem,
  BenchmarkOkResponse,
  DriftEntry,
  EvolutionResponse,
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

async function sendJson<T extends z.ZodTypeAny>(
  method: "POST" | "DELETE",
  url: string,
  schema: T,
  body?: unknown,
): Promise<z.infer<T>> {
  const init: RequestInit = {
    method,
    headers: {
      accept: "application/json",
      ...(body !== undefined ? { "content-type": "application/json" } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  };
  const r = await fetch(url, init);
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
  benchmarks: () => getJson("/benchmarks", z.array(BenchmarkListItem)),
  benchmarkDetail: (benchmarkId: string) =>
    getJson(`/benchmarks/${benchmarkId}`, BenchmarkDetailResponse),
  benchmarkIngest: (report: unknown) =>
    sendJson("POST", "/benchmarks/_ingest", BenchmarkIngestResponse, report),
  benchmarkTag: (benchmarkId: string, tag: string) =>
    sendJson("POST", `/benchmarks/${benchmarkId}/tag`, BenchmarkOkResponse, { tag }),
  benchmarkDelete: (benchmarkId: string) =>
    sendJson("DELETE", `/benchmarks/${benchmarkId}`, BenchmarkOkResponse),
  stats: () => getJson("/stats", StatsResponse),
  evolution: () => getJson("/evolution", EvolutionResponse),
  manifest: () => getJson("/api/manifest", Manifest),
} as const;
