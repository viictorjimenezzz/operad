import { AttemptsSwimlane } from "@/components/algorithms/auto_researcher/attempts-swimlane";
import { PlanCard } from "@/components/algorithms/auto_researcher/plan-card";
import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { StatusDot } from "@/components/ui/status-dot";
import { useUrlState } from "@/hooks/use-url-state";
import { hashColor } from "@/lib/hash-color";
import { IterationsResponse, RunSummary as RunSummarySchema } from "@/lib/types";
import type { RunSummary } from "@/lib/types";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { z } from "zod";

type IterationEntry = IterationsResponse["iterations"][number];

interface PlanEvent {
  attemptIndex: number | null;
  plan: unknown;
}

interface BestAttempt {
  attemptIndex: number | null;
  iterIndex: number;
  score: number;
}

export function AutoResearcherDetailOverview({
  dataSummary,
  dataIterations,
  dataEvents,
  dataChildren,
}: {
  dataSummary?: unknown;
  dataIterations?: unknown;
  dataEvents?: unknown;
  dataChildren?: unknown;
}) {
  const summaryParsed = RunSummarySchema.safeParse(dataSummary);
  const iterationsParsed = IterationsResponse.safeParse(dataIterations);
  const summary = summaryParsed.success ? summaryParsed.data : null;
  const iterations = iterationsParsed.success ? iterationsParsed.data : null;
  const events = parseEvents(dataEvents);
  const childCount = parseChildren(dataChildren).length;
  const start = algoStart(events);
  const best = bestAttempt(iterations?.iterations ?? []);

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border bg-bg-1 px-3 py-2 text-[12px]">
        <span className="inline-flex items-center gap-2 font-medium text-text">
          <StatusDot state={summary?.state ?? "running"} />
          {summary?.state ?? "running"}
        </span>
        <span className="text-muted">
          attempts{" "}
          <span className="font-mono text-text">{start.n ?? attemptCount(iterations)}</span>
        </span>
        <span className="text-muted">
          max_iter{" "}
          <span className="font-mono text-text">
            {iterations?.max_iter ?? start.maxIter ?? "n/a"}
          </span>
        </span>
        <span className="text-muted">
          threshold{" "}
          <span className="font-mono text-text">
            {formatScore(iterations?.threshold ?? start.threshold ?? null)}
          </span>
        </span>
        <span className="text-muted">
          best score <span className="font-mono text-text">{formatScore(best?.score ?? null)}</span>
        </span>
        <span className="text-muted">
          wall{" "}
          <span className="font-mono text-text">
            {formatDuration(summary?.duration_ms ?? null)}
          </span>
        </span>
        <span className="text-muted">
          child runs <span className="font-mono text-text">{childCount}</span>
        </span>
      </div>

      <section className="rounded-lg border border-border bg-bg-1 p-3">
        <div className="mb-2 text-[12px] font-medium text-text">Score vs iteration</div>
        <AttemptScoreOverlay data={dataIterations} threshold={iterations?.threshold ?? null} />
      </section>

      <section className="rounded-lg border border-border bg-bg-1 p-4">
        <div className="mb-2 text-[13px] font-semibold text-text">Best attempt</div>
        {best ? (
          <div className="flex flex-wrap items-center gap-3 text-[12px] text-muted">
            <span>
              Attempt{" "}
              <span className="font-mono text-text">
                {best.attemptIndex == null ? "unknown" : `#${best.attemptIndex + 1}`}
              </span>
            </span>
            <span>
              reached <span className="font-mono text-text">{best.score.toFixed(2)}</span>
            </span>
            <span>
              at iter <span className="font-mono text-text">{best.iterIndex}</span>
            </span>
            <TabLink tab="plan">View full plan</TabLink>
            <TabLink tab="best">View final answer</TabLink>
          </div>
        ) : (
          <EmptyState
            title="best attempt pending"
            description="reasoning scores have not been emitted yet"
            className="min-h-24"
          />
        )}
      </section>
    </div>
  );
}

export function AutoResearcherPlanTab({
  dataEvents,
  dataChildren,
}: {
  dataEvents?: unknown;
  dataChildren?: unknown;
}) {
  const events = parseEvents(dataEvents);
  const plans = planEvents(events);
  const children = parseChildren(dataChildren);
  const retrievers = children.filter((child) =>
    (child.root_agent_path ?? "").toLowerCase().includes("retriev"),
  );
  const retrieverEvidence = useRetrieverEvidence(retrievers);

  if (plans.length === 0) {
    return (
      <EmptyState
        title="plans not available"
        description="this run predates the AutoResearcher plan event; new runs emit one plan per attempt"
      />
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      {plans.map((plan, index) => {
        const retriever = retrievers[index] ?? null;
        const payloadEvidence = evidenceFromPlan(plan.plan);
        return (
          <PlanCard
            key={`${plan.attemptIndex ?? "unknown"}-${index}`}
            attemptIndex={plan.attemptIndex}
            plan={plan.plan}
            evidence={
              payloadEvidence.length > 0 ? payloadEvidence : (retrieverEvidence[index] ?? [])
            }
            retrieverHrefs={retriever ? [childHref(retriever)] : []}
          />
        );
      })}
    </div>
  );
}

export function AutoResearcherBestAnswer({
  dataChildren,
}: {
  dataChildren?: unknown;
}) {
  const children = parseChildren(dataChildren);
  const reasoner = [...children]
    .reverse()
    .find((child) => (child.root_agent_path ?? "").toLowerCase().includes("reason"));
  const answer = useChildAnswer(reasoner ?? null);

  return (
    <div className="h-full overflow-auto p-4">
      <section className="rounded-lg border border-border bg-bg-1 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="m-0 text-[15px] font-semibold text-text">Best answer</h2>
            <p className="m-0 mt-1 text-[11px] text-muted">Final selected reasoner output</p>
          </div>
          {reasoner ? (
            <a
              className="rounded border border-border px-2 py-1 text-[11px] text-text transition-colors hover:border-border-strong hover:bg-bg-2"
              href={childHref(reasoner)}
            >
              Open reasoner run
            </a>
          ) : null}
        </div>
        {answer.loading ? (
          <div className="h-32 animate-pulse rounded bg-bg-2" />
        ) : answer.answer ? (
          <MarkdownView value={answer.answer} />
        ) : (
          <EmptyState
            title="best answer not available"
            description="the selected reasoner child run has not emitted an answer yet"
            className="min-h-40"
          />
        )}
      </section>
    </div>
  );
}

export function AutoResearcherAttemptsTab({
  dataIterations,
  dataChildren,
}: {
  dataIterations?: unknown;
  dataChildren?: unknown;
}) {
  return <AttemptsSwimlane data={dataIterations} dataChildren={dataChildren} />;
}

function AttemptScoreOverlay({
  data,
  threshold,
}: {
  data: unknown;
  threshold: number | null;
}) {
  const parsed = IterationsResponse.safeParse(data);
  const [, setAttempt] = useUrlState("attempt");
  const [, setSearchParams] = useSearchParams();
  if (!parsed.success || parsed.data.iterations.length === 0) {
    return <EmptyState title="no score data" description="iteration scores have not arrived yet" />;
  }

  const attempts = attemptIndexes(parsed.data.iterations);
  if (attempts.length === 0) {
    return (
      <EmptyState
        title="attempt overlay unavailable"
        description="legacy runs do not emit attempt_index, so scores cannot be overlaid by attempt"
        className="min-h-48"
      />
    );
  }

  const rows = overlayRows(parsed.data.iterations, attempts);
  const pinAttempt = (attempt: number) => {
    setAttempt(String(attempt));
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("tab", "attempts");
        next.set("attempt", String(attempt));
        return next;
      },
      { replace: true },
    );
  };

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={rows} margin={{ top: 10, right: 24, bottom: 8, left: 0 }}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="iter" tick={{ fontSize: 11, fill: "var(--color-muted)" }} />
        <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "var(--color-muted)" }} />
        <Tooltip
          contentStyle={{
            background: "var(--color-bg-2)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            fontSize: 11,
          }}
        />
        {threshold != null ? (
          <ReferenceLine
            y={threshold}
            stroke="var(--color-ok)"
            strokeDasharray="4 4"
            label={{ value: "threshold", position: "right", fontSize: 10, fill: "var(--color-ok)" }}
          />
        ) : null}
        {attempts.map((attempt) => (
          <Line
            key={attempt}
            type="monotone"
            dataKey={`attempt_${attempt}`}
            name={`attempt ${attempt + 1}`}
            stroke={hashColor(`auto-researcher-${attempt}`)}
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
            onClick={() => pinAttempt(attempt)}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function TabLink({ tab, children }: { tab: string; children: string }) {
  const [, setSearchParams] = useSearchParams();
  return (
    <button
      type="button"
      className="rounded border border-border px-2 py-1 text-[11px] text-text transition-colors hover:border-border-strong hover:bg-bg-2"
      onClick={() =>
        setSearchParams(
          (current) => {
            const next = new URLSearchParams(current);
            next.set("tab", tab);
            return next;
          },
          { replace: true },
        )
      }
    >
      {children}
    </button>
  );
}

function parseEvents(data: unknown): unknown[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).events)) {
    return (data as Record<string, unknown>).events as unknown[];
  }
  return [];
}

function parseChildren(data: unknown): RunSummary[] {
  const raw = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).children)
      ? (data as Record<string, unknown>).children
      : [];
  const parsed = z.array(RunSummarySchema).safeParse(raw);
  return parsed.success ? parsed.data : [];
}

function algoStart(events: unknown[]): {
  n: number | null;
  maxIter: number | null;
  threshold: number | null;
} {
  const event = events.find((item) => {
    if (!item || typeof item !== "object") return false;
    const record = item as Record<string, unknown>;
    return record.type === "algo_event" && record.kind === "algo_start";
  });
  const payload =
    event && typeof event === "object" ? (event as Record<string, unknown>).payload : null;
  if (!payload || typeof payload !== "object") return { n: null, maxIter: null, threshold: null };
  const record = payload as Record<string, unknown>;
  return {
    n: typeof record.n === "number" ? record.n : null,
    maxIter: typeof record.max_iter === "number" ? record.max_iter : null,
    threshold: typeof record.threshold === "number" ? record.threshold : null,
  };
}

function planEvents(events: unknown[]): PlanEvent[] {
  return events
    .filter((item) => {
      if (!item || typeof item !== "object") return false;
      const record = item as Record<string, unknown>;
      return record.type === "algo_event" && record.kind === "plan";
    })
    .map((item) => {
      const payload = (item as Record<string, unknown>).payload;
      const record =
        payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
      return {
        attemptIndex: typeof record.attempt_index === "number" ? record.attempt_index : null,
        plan: record.plan,
      };
    });
}

function evidenceFromPlan(plan: unknown): string[] {
  if (!plan || typeof plan !== "object") return [];
  const record = plan as Record<string, unknown>;
  const raw = record.evidence ?? record.retrieved_evidence ?? record.hits;
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => (typeof item === "string" ? item : JSON.stringify(item)));
}

function attemptIndexes(entries: IterationEntry[]): number[] {
  return [
    ...new Set(
      entries
        .map((entry) =>
          typeof entry.metadata.attempt_index === "number" ? entry.metadata.attempt_index : null,
        )
        .filter((attempt): attempt is number => attempt != null),
    ),
  ].sort((a, b) => a - b);
}

function overlayRows(
  entries: IterationEntry[],
  attempts: number[],
): Array<Record<string, number | null>> {
  const iters = [...new Set(entries.map((entry) => entry.iter_index))].sort((a, b) => a - b);
  return iters.map((iter) => {
    const row: Record<string, number | null> = { iter };
    for (const attempt of attempts) {
      const score =
        [...entries]
          .reverse()
          .find(
            (entry) =>
              entry.iter_index === iter &&
              entry.metadata.attempt_index === attempt &&
              entry.score != null,
          )?.score ?? null;
      row[`attempt_${attempt}`] = score;
    }
    return row;
  });
}

function bestAttempt(entries: IterationEntry[]): BestAttempt | null {
  let best: BestAttempt | null = null;
  for (const entry of entries) {
    if (entry.score == null) continue;
    if (best && entry.score <= best.score) continue;
    best = {
      attemptIndex:
        typeof entry.metadata.attempt_index === "number" ? entry.metadata.attempt_index : null,
      iterIndex: entry.iter_index,
      score: entry.score,
    };
  }
  return best;
}

function attemptCount(data: IterationsResponse | null): number | string {
  if (!data) return "n/a";
  const attempts = attemptIndexes(data.iterations);
  return attempts.length > 0 ? attempts.length : "unknown";
}

function useChildAnswer(child: RunSummary | null): { answer: string | null; loading: boolean } {
  const query = useQuery({
    queryKey: ["algorithm", "auto-researcher", "answer", child?.run_id] as const,
    queryFn: async () => {
      if (!child) return null;
      const response = await fetch(`/runs/${child.run_id}/invocations`);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return extractLatestOutput(await response.json());
    },
    enabled: child != null,
  });
  return { answer: query.data ?? null, loading: query.isLoading };
}

function useRetrieverEvidence(children: RunSummary[]): string[][] {
  const queries = useQueries({
    queries: children.map((child) => ({
      queryKey: ["algorithm", "auto-researcher", "retriever", child.run_id] as const,
      queryFn: async () => {
        const response = await fetch(`/runs/${child.run_id}/invocations`);
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        return extractLatestEvidence(await response.json());
      },
    })),
  });
  return queries.map((query) => query.data ?? []);
}

function extractLatestEvidence(data: unknown): string[] {
  if (!data || typeof data !== "object") return [];
  const invocations = (data as Record<string, unknown>).invocations;
  if (!Array.isArray(invocations)) return [];
  for (let i = invocations.length - 1; i >= 0; i--) {
    const invocation = invocations[i];
    if (!invocation || typeof invocation !== "object") continue;
    const output = (invocation as Record<string, unknown>).output;
    const evidence = evidenceFromOutput(output);
    if (evidence.length > 0) return evidence;
  }
  return [];
}

function evidenceFromOutput(output: unknown): string[] {
  if (Array.isArray(output)) return output.map(formatEvidenceItem);
  if (!output || typeof output !== "object") return [];
  const record = output as Record<string, unknown>;
  for (const key of ["hits", "items", "documents", "results"]) {
    const value = record[key];
    if (Array.isArray(value)) return value.map(formatEvidenceItem);
  }
  return [];
}

function formatEvidenceItem(item: unknown): string {
  if (typeof item === "string") return item;
  if (!item || typeof item !== "object") return String(item);
  const record = item as Record<string, unknown>;
  const label = record.source ?? record.id ?? record.title ?? "evidence";
  const text = record.text ?? record.content ?? record.snippet ?? record.summary;
  return text == null ? String(label) : `${String(label)}: ${String(text)}`;
}

function extractLatestOutput(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const invocations = (data as Record<string, unknown>).invocations;
  if (!Array.isArray(invocations)) return null;
  for (let i = invocations.length - 1; i >= 0; i--) {
    const invocation = invocations[i];
    if (!invocation || typeof invocation !== "object") continue;
    const output = (invocation as Record<string, unknown>).output;
    const text = outputText(output);
    if (text) return text;
  }
  return null;
}

function outputText(output: unknown): string | null {
  if (typeof output === "string") return output;
  if (!output || typeof output !== "object") return null;
  const record = output as Record<string, unknown>;
  for (const key of ["answer", "text", "content"]) {
    const value = record[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}

function childHref(child: RunSummary): string {
  const identity = child.root_agent_path ?? child.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(child.run_id)}`;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}

function formatDuration(ms: number | null): string {
  if (ms == null) return "n/a";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}
