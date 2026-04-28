import {
  AgentEventsResponse,
  AgentGraphResponse,
  AgentGroupDetail,
  AgentGroupMetricsResponse,
  AgentGroupParametersResponse,
  AgentGroupSummary,
  AgentInvocationDiffResponse,
  AgentInvocationsResponse,
  type AgentInvokeRequest,
  AgentInvokeResponse,
  AgentMetaResponse,
  AgentParametersResponse,
  AgentPromptsResponse,
  AgentValuesResponse,
  AlgorithmGroup,
  ArchivedRunRecord,
  BenchmarkDetailResponse,
  BenchmarkIngestResponse,
  BenchmarkListItem,
  BenchmarkOkResponse,
  CassetteDeterminismResponse,
  CassettePreviewResponse,
  CassetteReplayResponse,
  CassetteSummary,
  DebateRoundsResponse,
  DriftEntry,
  EvolutionResponse,
  FitnessEntry,
  GradientEntry,
  GraphResponse,
  IoGraphResponse,
  IterationsResponse,
  Manifest,
  MutationsMatrix,
  ProgressSnapshot,
  RunEventsResponse,
  RunInvocationsResponse,
  RunNotesResponse,
  RunSummary,
  StatsResponse,
  TrainingGroup,
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
  method: "POST" | "PATCH" | "DELETE",
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

async function postJson<T extends z.ZodTypeAny>(
  url: string,
  body: unknown,
  schema: T,
): Promise<z.infer<T>> {
  return sendJson("POST", url, schema, body);
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
  runsByHash: (hashContent: string) =>
    getJson(
      `/runs/by-hash?hash_content=${encodeURIComponent(hashContent)}`,
      z.object({ matches: z.array(RunSummary) }),
    ),
  runLayout: (runId: string, tab: "overview" | "graph" | "invocations") =>
    getJson(`/runs/${runId}/layout/${tab}`, z.unknown()),
  runChildren: (runId: string) => getJson(`/runs/${runId}/children`, z.array(RunSummary)),
  agentGroups: () => getJson("/api/agents", z.array(AgentGroupSummary)),
  agentGroup: (hashContent: string) =>
    getJson(`/api/agents/${encodeURIComponent(hashContent)}`, AgentGroupDetail),
  agentGroupRuns: (hashContent: string) =>
    getJson(`/api/agents/${encodeURIComponent(hashContent)}/runs`, z.array(RunSummary)),
  agentGroupMetrics: (hashContent: string) =>
    getJson(`/api/agents/${encodeURIComponent(hashContent)}/metrics`, AgentGroupMetricsResponse),
  agentGroupParameters: (hashContent: string) =>
    getJson(
      `/api/agents/${encodeURIComponent(hashContent)}/parameters`,
      AgentGroupParametersResponse,
    ),
  algorithmGroups: () => getJson("/api/algorithms", z.array(AlgorithmGroup)),
  oproGroups: () => getJson("/api/opro", z.array(AlgorithmGroup)),
  trainingGroups: () => getJson("/api/trainings", z.array(TrainingGroup)),
  runSummary: (runId: string) => getJson(`/runs/${runId}/summary`, RunSummary),
  runInvocations: (runId: string) => getJson(`/runs/${runId}/invocations`, RunInvocationsResponse),
  patchRunNotes: (runId: string, markdown: string) =>
    sendJson("PATCH", `/api/runs/${encodeURIComponent(runId)}/notes`, RunNotesResponse, {
      markdown,
    }),
  runIoGraph: (runId: string) => getJson(`/runs/${runId}/io_graph`, IoGraphResponse),
  runAgentGraph: (runId: string) => getJson(`/runs/${runId}/agent_graph`, AgentGraphResponse),
  agentInvocations: (runId: string, agentPath: string) =>
    getJson(
      `/runs/${runId}/agent/${encodeURIComponent(agentPath)}/invocations`,
      AgentInvocationsResponse,
    ),
  agentMeta: (runId: string, agentPath: string) =>
    getJson(`/runs/${runId}/agent/${encodeURIComponent(agentPath)}/meta`, AgentMetaResponse),
  agentParameters: (runId: string, agentPath: string) =>
    getJson(
      `/runs/${runId}/agent/${encodeURIComponent(agentPath)}/parameters`,
      AgentParametersResponse,
    ),
  agentDiff: (runId: string, agentPath: string, fromInvocationId: string, toInvocationId: string) =>
    getJson(
      `/runs/${runId}/agent/${encodeURIComponent(agentPath)}/diff?from=${encodeURIComponent(fromInvocationId)}&to=${encodeURIComponent(toInvocationId)}`,
      AgentInvocationDiffResponse,
    ),
  agentValues: (runId: string, agentPath: string, attr: string, side: "in" | "out") =>
    getJson(
      `/runs/${runId}/agent/${encodeURIComponent(agentPath)}/values?attr=${encodeURIComponent(attr)}&side=${side}`,
      AgentValuesResponse,
    ),
  agentPrompts: (runId: string, agentPath: string) =>
    getJson(`/runs/${runId}/agent/${encodeURIComponent(agentPath)}/prompts`, AgentPromptsResponse),
  agentEvents: (runId: string, agentPath: string, limit = 500) =>
    getJson(
      `/runs/${runId}/agent/${encodeURIComponent(agentPath)}/events?limit=${limit}`,
      AgentEventsResponse,
    ),
  agentInvoke: (runId: string, agentPath: string, body: AgentInvokeRequest) =>
    postJson(
      `/runs/${runId}/agent/${encodeURIComponent(agentPath)}/invoke`,
      body,
      AgentInvokeResponse,
    ),
  runEvents: (runId: string, limit = 500) =>
    getJson(`/runs/${runId}/events?limit=${limit}`, RunEventsResponse),
  graph: (runId: string) => getJson(`/graph/${runId}`, GraphResponse),
  fitness: (runId: string) => getJson(`/runs/${runId}/fitness.json`, z.array(FitnessEntry)),
  iterations: (runId: string) => getJson(`/runs/${runId}/iterations.json`, IterationsResponse),
  debate: (runId: string) => getJson(`/runs/${runId}/debate.json`, DebateRoundsResponse),
  mutations: (runId: string) => getJson(`/runs/${runId}/mutations.json`, MutationsMatrix),
  drift: (runId: string) => getJson(`/runs/${runId}/drift.json`, z.array(DriftEntry)),
  progress: (runId: string) => getJson(`/runs/${runId}/progress.json`, ProgressSnapshot),
  gradients: (runId: string) => getJson(`/runs/${runId}/gradients.json`, z.array(GradientEntry)),
  benchmarks: () => getJson("/api/benchmarks", z.array(BenchmarkListItem)),
  benchmarkDetail: (benchmarkId: string) =>
    getJson(`/api/benchmarks/${benchmarkId}`, BenchmarkDetailResponse),
  benchmarkIngest: (report: unknown) =>
    sendJson("POST", "/api/benchmarks/_ingest", BenchmarkIngestResponse, report),
  benchmarkTag: (benchmarkId: string, tag: string) =>
    sendJson("POST", `/api/benchmarks/${benchmarkId}/tag`, BenchmarkOkResponse, { tag }),
  benchmarkDelete: (benchmarkId: string) =>
    sendJson("DELETE", `/api/benchmarks/${benchmarkId}`, BenchmarkOkResponse),
  stats: () => getJson("/stats", StatsResponse),
  evolution: () => getJson("/evolution", EvolutionResponse),
  cassettes: () => getJson("/api/cassettes", z.array(CassetteSummary)),
  cassetteReplay: (params: { path: string; runIdOverride?: string; delayMs?: number }) =>
    postJson(
      `/api/cassettes/replay?delay_ms=${params.delayMs ?? 50}`,
      { path: params.path, run_id_override: params.runIdOverride ?? null },
      CassetteReplayResponse,
    ),
  cassetteDeterminism: (path: string) =>
    postJson("/api/cassettes/determinism-check", { path }, CassetteDeterminismResponse),
  cassettePreview: (path: string, limit = 100) =>
    getJson(
      `/api/cassettes/preview?path=${encodeURIComponent(path)}&limit=${limit}`,
      CassettePreviewResponse,
    ),
  manifest: () => getJson("/api/manifest", Manifest),
  archive: (params: { from?: number; to?: number; algorithm?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params.from != null) qs.set("from", String(params.from));
    if (params.to != null) qs.set("to", String(params.to));
    if (params.algorithm) qs.set("algorithm", params.algorithm);
    if (params.limit != null) qs.set("limit", String(params.limit));
    const suffix = qs.size > 0 ? `?${qs.toString()}` : "";
    return getJson(`/api/archive${suffix}`, z.array(RunSummary));
  },
  archivedRun: (runId: string) => getJson(`/api/archive/${runId}`, ArchivedRunRecord),
  restoreArchivedRun: async (runId: string) => {
    const url = `/api/archive/${runId}/restore`;
    const r = await fetch(url, { method: "POST", headers: { accept: "application/json" } });
    if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← ${url}`);
    const raw: unknown = await r.json();
    const parsed = z.object({ ok: z.boolean(), run: RunSummary }).safeParse(raw);
    if (!parsed.success) throw new ParseError(url, parsed.error);
    return parsed.data;
  },
  deleteArchivedRun: async (runId: string) => {
    const r = await fetch(`/api/archive/${runId}`, { method: "DELETE" });
    if (!r.ok) throw new HttpError(r.status, `${r.status} ${r.statusText} ← /api/archive/${runId}`);
    const raw: unknown = await r.json();
    const parsed = z.object({ ok: z.boolean() }).safeParse(raw);
    if (!parsed.success) throw new ParseError(`/api/archive/${runId}`, parsed.error);
    return parsed.data;
  },
  exportArchiveJsonl: async () => {
    const r = await fetch("/api/archive/_export?format=jsonl", {
      method: "POST",
      headers: { accept: "application/x-ndjson" },
    });
    if (!r.ok)
      throw new HttpError(r.status, `${r.status} ${r.statusText} ← /api/archive/_export?format=jsonl`);
    return r.text();
  },
} as const;
