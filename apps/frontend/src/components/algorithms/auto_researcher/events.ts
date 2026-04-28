import { IterationsResponse } from "@/lib/types";

export type AutoResearcherPhase = "plan" | "retrieve" | "reason" | "critique" | "reflect";

export interface AutoResearcherPhaseCell {
  phase: AutoResearcherPhase;
  score: number | null;
  text: string;
}

export interface AutoResearcherAttempt {
  attemptIndex: number | null;
  plan: unknown;
  evidence: string[];
  cells: Partial<Record<AutoResearcherPhase, AutoResearcherPhaseCell>>;
  bestScore: number | null;
  finalReasoning: string | null;
  finalAnswer: string | null;
}

const PHASES_FROM_AGENT: Array<[AutoResearcherPhase, string]> = [
  ["retrieve", "retriev"],
  ["reason", "reason"],
  ["critique", "critic"],
  ["reflect", "reflect"],
];

export const AUTO_RESEARCHER_PHASES: AutoResearcherPhase[] = [
  "plan",
  "retrieve",
  "reason",
  "critique",
  "reflect",
];

export function buildAutoResearcherAttempts(
  dataEvents: unknown,
  dataIterations?: unknown,
): AutoResearcherAttempt[] {
  const events = parseEvents(dataEvents);
  const iterations = readIterations(dataIterations);
  const attempts = new Map<string, AutoResearcherAttempt>();
  const order: Array<number | null> = [];

  const ensure = (attemptIndex: number | null): AutoResearcherAttempt => {
    const key = attemptKey(attemptIndex);
    const existing = attempts.get(key);
    if (existing) return existing;
    const attempt: AutoResearcherAttempt = {
      attemptIndex,
      plan: null,
      evidence: [],
      cells: {},
      bestScore: null,
      finalReasoning: null,
      finalAnswer: null,
    };
    attempts.set(key, attempt);
    order.push(attemptIndex);
    return attempt;
  };

  for (const event of events) {
    const record = asRecord(event);
    if (!record || record.type !== "algo_event") continue;
    const payload = asRecord(record.payload);
    if (!payload) continue;

    if (record.kind === "plan") {
      const attempt = ensure(readAttemptIndex(payload));
      attempt.plan = payload.plan ?? payload;
      setCell(attempt, "plan", null, planToMarkdown(attempt.plan));
    }
  }

  for (const entry of iterations) {
    ensure(readAttemptIndex(entry.metadata));
  }

  const knownOrder = order.length > 0 ? [...order] : [null];
  const cursors: Partial<Record<AutoResearcherPhase, number>> = {};

  for (const event of events) {
    const record = asRecord(event);
    if (!record || record.type !== "agent_event" || record.kind !== "end") continue;
    const phase = phaseForAgent(record.agent_path);
    if (!phase) continue;

    const cursor = cursors[phase] ?? 0;
    cursors[phase] = cursor + 1;
    const attempt = ensure(knownOrder[cursor % knownOrder.length] ?? null);
    const response = responsePayload(record.output);
    const score = numericField(response, "score");

    if (phase === "retrieve") {
      const evidence = evidenceFromOutput(response);
      if (evidence.length > 0) attempt.evidence = evidence;
      setCell(attempt, phase, score, evidenceText(evidence, response));
      continue;
    }

    if (phase === "reason") {
      const reasoning = stringField(response, "reasoning");
      const answer = stringField(response, "answer");
      if (reasoning) attempt.finalReasoning = reasoning;
      if (answer) attempt.finalAnswer = answer;
      setCell(attempt, phase, score, reasonText(response));
      continue;
    }

    setCell(attempt, phase, score, responseText(response, phase));
  }

  for (const entry of iterations) {
    const phase = normalizePhase(entry.phase);
    if (!phase) continue;
    const attempt = ensure(readAttemptIndex(entry.metadata));
    const existing = attempt.cells[phase];
    setCell(
      attempt,
      phase,
      typeof entry.score === "number" ? entry.score : (existing?.score ?? null),
      existing?.text || iterationText(entry),
    );
  }

  return orderedAttempts(attempts, order);
}

export function selectBestAttempt(
  attempts: AutoResearcherAttempt[],
  terminalScore: number | null,
): AutoResearcherAttempt | null {
  const scored = attempts.filter((attempt) => attempt.bestScore != null);
  if (scored.length === 0) return attempts[0] ?? null;

  if (terminalScore != null) {
    return (
      [...scored].sort((a, b) => {
        const aDelta = Math.abs((a.bestScore ?? 0) - terminalScore);
        const bDelta = Math.abs((b.bestScore ?? 0) - terminalScore);
        if (aDelta !== bDelta) return aDelta - bDelta;
        return (
          (b.bestScore ?? Number.NEGATIVE_INFINITY) - (a.bestScore ?? Number.NEGATIVE_INFINITY)
        );
      })[0] ?? null
    );
  }

  return (
    [...scored].sort(
      (a, b) =>
        (b.bestScore ?? Number.NEGATIVE_INFINITY) - (a.bestScore ?? Number.NEGATIVE_INFINITY),
    )[0] ?? null
  );
}

export function readTerminalScore(summary: unknown): number | null {
  const record = asRecord(summary);
  const value = record?.algorithm_terminal_score;
  return typeof value === "number" ? value : null;
}

export function planToMarkdown(plan: unknown): string {
  if (typeof plan === "string") return plan;
  const record = asRecord(plan);
  if (!record) return "";
  return flattenObject(record)
    .map(([key, value]) => `- **${key}:** ${formatValue(value)}`)
    .join("\n");
}

function setCell(
  attempt: AutoResearcherAttempt,
  phase: AutoResearcherPhase,
  score: number | null,
  text: string,
) {
  const current = attempt.cells[phase];
  attempt.cells[phase] = {
    phase,
    score: score ?? current?.score ?? null,
    text: text || current?.text || "No phase output emitted.",
  };
  const cellScore = attempt.cells[phase]?.score;
  if (typeof cellScore === "number") {
    attempt.bestScore =
      attempt.bestScore == null ? cellScore : Math.max(attempt.bestScore, cellScore);
  }
}

function parseEvents(data: unknown): unknown[] {
  if (Array.isArray(data)) return data;
  const record = asRecord(data);
  return Array.isArray(record?.events) ? record.events : [];
}

function readIterations(data: unknown): IterationsResponse["iterations"] {
  const parsed = IterationsResponse.safeParse(data);
  return parsed.success ? parsed.data.iterations : [];
}

function readAttemptIndex(record: unknown): number | null {
  const attemptIndex = asRecord(record)?.attempt_index;
  return typeof attemptIndex === "number" ? attemptIndex : null;
}

function normalizePhase(phase: string | null): AutoResearcherPhase | null {
  switch (phase) {
    case "plan":
    case "retrieve":
    case "reason":
    case "critique":
    case "reflect":
      return phase;
    case "retriever":
      return "retrieve";
    case "critic":
      return "critique";
    case "reflector":
      return "reflect";
    default:
      return null;
  }
}

function phaseForAgent(agentPath: unknown): AutoResearcherPhase | null {
  if (typeof agentPath !== "string") return null;
  const value = agentPath.toLowerCase();
  return PHASES_FROM_AGENT.find(([, token]) => value.includes(token))?.[0] ?? null;
}

function responsePayload(output: unknown): unknown {
  const record = asRecord(output);
  return record && "response" in record ? record.response : output;
}

function reasonText(response: unknown): string {
  const reasoning = stringField(response, "reasoning");
  const answer = stringField(response, "answer");
  const parts = [
    reasoning ? `**Reasoning**\n\n${reasoning}` : null,
    answer ? `**Answer**\n\n${answer}` : null,
  ].filter((part): part is string => part != null);
  return parts.length > 0 ? parts.join("\n\n") : responseText(response, "reason");
}

function responseText(response: unknown, phase: AutoResearcherPhase): string {
  if (typeof response === "string") return response;
  const record = asRecord(response);
  if (!record) return response == null ? "No phase output emitted." : String(response);

  if (phase === "critique") {
    const rationale = stringField(record, "rationale");
    const score = numericField(record, "score");
    return [
      score == null ? null : `score: ${score.toFixed(2)}`,
      rationale ? `rationale: ${rationale}` : null,
    ]
      .filter((part): part is string => part != null)
      .join("\n\n");
  }

  if (phase === "reflect") {
    const deficiencies = record.deficiencies;
    const needsRevision = record.needs_revision;
    const revision = stringField(record, "suggested_revision");
    return [
      Array.isArray(deficiencies) && deficiencies.length > 0
        ? `deficiencies:\n${deficiencies.map((item) => `- ${String(item)}`).join("\n")}`
        : null,
      typeof needsRevision === "boolean" ? `needs_revision: ${String(needsRevision)}` : null,
      revision ? `suggested_revision: ${revision}` : null,
    ]
      .filter((part): part is string => part != null)
      .join("\n\n");
  }

  for (const key of ["text", "output", "message", "content", "answer", "reasoning"]) {
    const value = stringField(record, key);
    if (value) return value;
  }

  return JSON.stringify(record, null, 2);
}

function evidenceText(evidence: string[], response: unknown): string {
  if (evidence.length > 0) return evidence.map((item) => `- ${item}`).join("\n");
  return responseText(response, "retrieve");
}

function evidenceFromOutput(output: unknown): string[] {
  const record = asRecord(output);
  if (!record) return Array.isArray(output) ? output.map(formatEvidenceItem) : [];
  for (const key of ["items", "documents", "results"]) {
    const value = record[key];
    if (Array.isArray(value)) return value.map(formatEvidenceItem);
  }
  const hits = asRecord(record.hits);
  if (Array.isArray(hits?.items)) return hits.items.map(formatEvidenceItem);
  return [];
}

function formatEvidenceItem(item: unknown): string {
  if (typeof item === "string") return item;
  const record = asRecord(item);
  if (!record) return String(item);
  const source = record.source ?? record.id ?? record.title;
  const text = record.text ?? record.content ?? record.snippet ?? record.summary;
  const score = numericField(record, "score");
  return [
    source == null ? null : String(source),
    text == null ? null : String(text),
    score == null ? null : `score ${score.toFixed(2)}`,
  ]
    .filter((part): part is string => part != null)
    .join(" - ");
}

function iterationText(entry: IterationsResponse["iterations"][number]): string {
  if (entry.text) return entry.text;
  const metadata = entry.metadata;
  for (const key of ["text", "output", "reasoning", "answer", "rationale", "suggested_revision"]) {
    const value = metadata[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return entry.score == null ? "No phase output emitted." : "score recorded";
}

function orderedAttempts(
  attempts: Map<string, AutoResearcherAttempt>,
  order: Array<number | null>,
): AutoResearcherAttempt[] {
  const seen = new Set<string>();
  const out: AutoResearcherAttempt[] = [];
  for (const attemptIndex of order) {
    const key = attemptKey(attemptIndex);
    const attempt = attempts.get(key);
    if (attempt && !seen.has(key)) {
      seen.add(key);
      out.push(attempt);
    }
  }
  const rest = [...attempts.entries()]
    .filter(([key]) => !seen.has(key))
    .map(([, attempt]) => attempt)
    .sort(
      (a, b) =>
        (a.attemptIndex ?? Number.MAX_SAFE_INTEGER) - (b.attemptIndex ?? Number.MAX_SAFE_INTEGER),
    );
  return [...out, ...rest];
}

function attemptKey(attemptIndex: number | null): string {
  return attemptIndex == null ? "unknown" : String(attemptIndex);
}

function stringField(value: unknown, key: string): string | null {
  const field = asRecord(value)?.[key];
  return typeof field === "string" && field.length > 0 ? field : null;
}

function numericField(value: unknown, key: string): number | null {
  const field = asRecord(value)?.[key];
  return typeof field === "number" && Number.isFinite(field) ? field : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function flattenObject(obj: Record<string, unknown>, prefix = ""): Array<[string, unknown]> {
  const rows: Array<[string, unknown]> = [];
  for (const [key, value] of Object.entries(obj)) {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      rows.push(...flattenObject(value as Record<string, unknown>, nextKey));
    } else {
      rows.push([nextKey, value]);
    }
  }
  return rows;
}

function formatValue(value: unknown): string {
  if (value == null) return "n/a";
  if (Array.isArray(value)) return value.map(formatValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
