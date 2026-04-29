import type { Candidate } from "@/lib/types";

export type BeamRankedCandidate = {
  candidate: Candidate;
  candidateIndex: number;
  rank: number;
  selected: boolean;
  previousText: string | undefined;
};

export type BeamAgentInvocation = {
  id: string;
  runId: string | null;
  agentPath: string;
  className: string;
  role: "generator" | "critic";
  state: "ended" | "error";
  startedAt: number | null;
  finishedAt: number | null;
  latencyMs: number | null;
  promptTokens: number | null;
  completionTokens: number | null;
  costUsd: number | null;
  backend: string | null;
  model: string | null;
  promptHash: string | null;
  hashContent: string | null;
  promptUser: string | null;
  input: unknown;
  output: unknown;
  responseText: string;
  criticInputText: string;
  rationale: string;
  score: number | null;
  langfuseUrl: string | null;
};

export type BeamCandidateDetail = BeamRankedCandidate & {
  generator: BeamAgentInvocation | null;
  critic: BeamAgentInvocation | null;
  prompt: string;
  answer: string;
  rationale: string;
  generatorLatencyMs: number | null;
  criticLatencyMs: number | null;
  totalLatencyMs: number | null;
  costUsd: number | null;
  promptTokens: number | null;
  completionTokens: number | null;
  langfuseUrl: string | null;
};

export function parseTopIndices(data: unknown): Set<number> {
  const rows = isRecord(data) && Array.isArray(data.iterations) ? data.iterations : [];
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    const metadata = isRecord(row) ? row.metadata : null;
    const top = isRecord(metadata) ? metadata.top_indices : null;
    if (Array.isArray(top)) {
      return new Set(top.filter((value): value is number => typeof value === "number"));
    }
  }
  return new Set();
}

export function rankBeamCandidates(
  candidates: Candidate[],
  topIndices: Set<number>,
): BeamRankedCandidate[] {
  const ranked = candidates
    .map((candidate, index) => ({
      candidate,
      candidateIndex: candidate.candidate_index ?? index,
    }))
    .sort((a, b) => {
      const scoreA = a.candidate.score ?? Number.NEGATIVE_INFINITY;
      const scoreB = b.candidate.score ?? Number.NEGATIVE_INFINITY;
      if (scoreA !== scoreB) return scoreB - scoreA;
      return a.candidateIndex - b.candidateIndex;
    });

  return ranked.map((entry, index) => ({
    ...entry,
    rank: index + 1,
    selected: topIndices.size > 0 ? topIndices.has(entry.candidateIndex) : index === 0,
    previousText: index > 0 ? (ranked[index - 1]?.candidate.text ?? undefined) : undefined,
  }));
}

export function agentsSummaryLangfuse(data: unknown): string | null {
  const agents = isRecord(data) && Array.isArray(data.agents) ? data.agents : [];
  for (const agent of agents) {
    const url = stringAt(agent, "langfuse_url");
    if (url) return url;
  }
  return null;
}

export function beamAgentInvocationsFromEvents(
  dataEvents: unknown,
  fallbackLangfuseUrl: string | null,
): BeamAgentInvocation[] {
  return normalizeEvents(dataEvents)
    .filter(
      (event) => event.type === "agent_event" && (event.kind === "end" || event.kind === "error"),
    )
    .sort((a, b) => (numberAt(a, "started_at") ?? 0) - (numberAt(b, "started_at") ?? 0))
    .map((event, index) => {
      const metadata = recordAt(event, "metadata");
      const output = recordAt(event, "output");
      const response = recordAt(output, "response") ?? output;
      const config = recordAt(metadata, "config");
      const startedAt = numberAt(event, "started_at");
      const finishedAt = numberAt(event, "finished_at");
      const agentPath = stringAt(event, "agent_path") ?? "Agent";
      const className = stringAt(metadata, "class_name") ?? agentPath.split(".").at(-1) ?? "Agent";
      const invokeId = stringAt(metadata, "invoke_id");
      const promptUser = stringAt(metadata, "prompt_user");
      const role = isCriticPath(agentPath) ? "critic" : "generator";

      return {
        id: invokeId ?? `${agentPath}:${index}`,
        runId: stringAt(event, "run_id"),
        agentPath,
        className,
        role,
        state: event.kind === "error" ? "error" : "ended",
        startedAt,
        finishedAt,
        latencyMs: numberAt(output, "latency_ms") ?? elapsedMs(startedAt, finishedAt),
        promptTokens: numberAt(output, "prompt_tokens"),
        completionTokens: numberAt(output, "completion_tokens"),
        costUsd: numberAt(output, "cost_usd"),
        backend: stringAt(output, "backend") ?? stringAt(config, "backend"),
        model: stringAt(output, "model") ?? stringAt(config, "model"),
        promptHash: stringAt(output, "hash_prompt"),
        hashContent: stringAt(metadata, "hash_content"),
        promptUser,
        input: event.input,
        output: response,
        responseText: textFromResponse(response),
        criticInputText: textFromCriticInput(event.input),
        rationale: textAt(response, "rationale", "critique", "feedback", "reasoning"),
        score: numberAt(response, "score"),
        langfuseUrl:
          stringAt(event, "langfuse_url") ??
          stringAt(metadata, "langfuse_url") ??
          stringAt(output, "langfuse_url") ??
          fallbackLangfuseUrl,
      };
    });
}

export function beamCandidateDetails(
  candidates: Candidate[],
  dataIterations: unknown,
  dataEvents: unknown,
  dataChildren: unknown,
  dataAgentsSummary: unknown,
): BeamCandidateDetail[] {
  const topIndices = parseTopIndices(dataIterations);
  const ranked = rankBeamCandidates(candidates, topIndices);
  const fallbackLangfuse = agentsSummaryLangfuse(dataAgentsSummary);
  const childLinks = childLangfuseByCandidate(dataChildren);
  const invocations = beamAgentInvocationsFromEvents(dataEvents, fallbackLangfuse);
  const generators = invocations.filter((invocation) => invocation.role === "generator");
  const critics = invocations.filter((invocation) => invocation.role === "critic");
  const usedGenerators = new Set<string>();
  const usedCritics = new Set<string>();

  return ranked.map((entry) => {
    const text = entry.candidate.text ?? "";
    const generator = takeInvocation(
      generators,
      usedGenerators,
      entry.candidateIndex,
      (invocation) => sameText(invocation.responseText, text),
    );
    const critic = takeInvocation(critics, usedCritics, entry.candidateIndex, (invocation) =>
      sameText(invocation.criticInputText, text),
    );
    const generatorLatencyMs = generator?.latencyMs ?? null;
    const criticLatencyMs = critic?.latencyMs ?? null;
    const totalLatencyMs = sumNumbers(generatorLatencyMs, criticLatencyMs);
    const costUsd = sumNumbers(generator?.costUsd ?? null, critic?.costUsd ?? null);
    const promptTokens = sumNumbers(generator?.promptTokens ?? null, critic?.promptTokens ?? null);
    const completionTokens = sumNumbers(
      generator?.completionTokens ?? null,
      critic?.completionTokens ?? null,
    );

    return {
      ...entry,
      generator,
      critic,
      prompt: generator?.promptUser ?? stringify(generator?.input),
      answer: text || generator?.responseText || "",
      rationale: critic?.rationale ?? "",
      generatorLatencyMs,
      criticLatencyMs,
      totalLatencyMs,
      costUsd,
      promptTokens,
      completionTokens,
      langfuseUrl:
        childLinks.get(entry.candidateIndex) ??
        generator?.langfuseUrl ??
        critic?.langfuseUrl ??
        fallbackLangfuse,
    };
  });
}

function takeInvocation(
  invocations: BeamAgentInvocation[],
  used: Set<string>,
  candidateIndex: number,
  match: (invocation: BeamAgentInvocation) => boolean,
): BeamAgentInvocation | null {
  const exact = invocations.find((invocation) => !used.has(invocation.id) && match(invocation));
  const byIndex = invocations[candidateIndex];
  const chosen =
    exact ??
    (byIndex && !used.has(byIndex.id) ? byIndex : null) ??
    invocations.find((invocation) => !used.has(invocation.id)) ??
    null;
  if (chosen) used.add(chosen.id);
  return chosen;
}

function childLangfuseByCandidate(data: unknown): Map<number, string> {
  const raw = Array.isArray(data)
    ? data
    : isRecord(data) && Array.isArray(data.children)
      ? data.children
      : [];
  const out = new Map<number, string>();
  raw.forEach((item, fallbackIndex) => {
    const url = stringAt(item, "langfuse_url");
    if (!url) return;
    const metadata = recordAt(item, "metadata");
    const algorithmMetadata = recordAt(item, "algorithm_metadata");
    const parentRunMetadata = recordAt(item, "parent_run_metadata");
    const index =
      numberAt(metadata, "candidate_index") ??
      numberAt(algorithmMetadata, "candidate_index") ??
      numberAt(parentRunMetadata, "candidate_index") ??
      fallbackIndex;
    out.set(index, url);
  });
  return out;
}

function normalizeEvents(data: unknown): Array<Record<string, unknown>> {
  const raw = Array.isArray(data)
    ? data
    : isRecord(data) && Array.isArray(data.events)
      ? data.events
      : [];
  return raw.filter(isRecord);
}

function textFromResponse(value: unknown): string {
  const record = asRecord(value);
  if (!record) return typeof value === "string" ? value : "";
  return textAt(record, "answer", "text", "candidate", "response");
}

function textFromCriticInput(value: unknown): string {
  const record = asRecord(value);
  const output = recordAt(record, "output");
  return textFromResponse(output);
}

function textAt(source: unknown, ...keys: string[]): string {
  for (const key of keys) {
    const value = stringAt(source, key);
    if (value) return value;
  }
  return "";
}

function sameText(left: string, right: string): boolean {
  const a = left.trim();
  const b = right.trim();
  return a.length > 0 && b.length > 0 && a === b;
}

function elapsedMs(startedAt: number | null, finishedAt: number | null): number | null {
  if (startedAt == null || finishedAt == null) return null;
  return Math.max(0, (finishedAt - startedAt) * 1000);
}

function sumNumbers(...values: Array<number | null>): number | null {
  const present = values.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (present.length === 0) return null;
  return present.reduce((sum, value) => sum + value, 0);
}

function stringify(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function isCriticPath(path: string): boolean {
  const lower = path.toLowerCase();
  return lower.includes("critic") || lower.includes("judge") || lower.includes("score");
}

function recordAt(source: unknown, key: string): Record<string, unknown> | null {
  const record = asRecord(source);
  return asRecord(record?.[key]);
}

function numberAt(source: unknown, key: string): number | null {
  const record = asRecord(source);
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringAt(source: unknown, key: string): string | null {
  const record = asRecord(source);
  const value = record?.[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
