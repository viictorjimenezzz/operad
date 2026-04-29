import { EmptyState, Pill } from "@/components/ui";
import { MarkdownView } from "@/components/ui/markdown";
import { useUrlState } from "@/hooks/use-url-state";
import {
  type AlgoEventEnvelope,
  IterationsResponse,
  RunEventsResponse,
  type RunSummary,
  RunSummary as RunSummarySchema,
} from "@/lib/types";
import { cn, formatCost, truncateMiddle } from "@/lib/utils";
import { Link } from "react-router-dom";
import { z } from "zod";

export interface OPROStep {
  iterIndex: number;
  stepIndex: number;
  paramPath: string;
  currentValue: string | null;
  candidateValue: string;
  historySize: number | null;
  score: number | null;
  accepted: boolean | null;
  proposedAt: number | null;
  evaluatedAt: number | null;
  proposerRun: RunSummary | null;
  evaluatorRun: RunSummary | null;
}

export function OPROHistoryTab({
  dataIterations,
  dataEvents,
  dataChildren,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
  dataChildren?: unknown;
}) {
  const steps = buildOPROSteps(dataIterations, dataEvents, dataChildren);
  const [stepParam, setStepParam] = useUrlState("step");
  const selected = parseStepParam(stepParam);

  if (steps.length === 0) {
    return (
      <EmptyState
        title="no OPRO steps"
        description="propose and evaluate iteration events have not arrived for this run"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <ol className="relative flex flex-col gap-4 border-l border-border pl-5">
        {steps.map((step, index) => {
          const history = steps
            .slice(0, index)
            .filter((item) => item.score != null)
            .slice(-(step.historySize ?? 8));
          return (
            <li key={`${step.iterIndex}-${step.stepIndex}`}>
              <StepCard
                step={step}
                history={history}
                selected={selected === step.stepIndex}
                onSelect={() => setStepParam(String(step.stepIndex))}
              />
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StepCard({
  step,
  history,
  selected,
  onSelect,
}: {
  step: OPROStep;
  history: OPROStep[];
  selected: boolean;
  onSelect: () => void;
}) {
  const accepted = step.accepted === true;
  const rejected = step.accepted === false;

  return (
    <section
      className={cn(
        "relative rounded-lg border bg-bg-1",
        selected ? "border-accent ring-1 ring-[--color-accent-dim]" : "border-border",
      )}
    >
      <span className="absolute -left-[27px] top-3 h-3 w-3 rounded-full border border-border bg-bg-1" />
      <button
        type="button"
        onClick={onSelect}
        className="flex w-full items-start justify-between gap-3 border-b border-border px-3 py-2 text-left transition-colors hover:bg-bg-2"
      >
        <div>
          <div className="text-[12px] font-medium text-text">step {step.stepIndex}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-muted">
            <span className="font-mono">{step.paramPath}</span>
            <span>score {formatScore(step.score)}</span>
            {step.historySize != null ? <span>history {step.historySize}</span> : null}
          </div>
        </div>
        {accepted ? (
          <Pill tone="ok">accepted</Pill>
        ) : rejected ? (
          <Pill tone="warn">rejected</Pill>
        ) : (
          <Pill tone="default">pending</Pill>
        )}
      </button>

      <div className="grid gap-4 p-3 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0 space-y-3">
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
              proposed
            </div>
            <div className="rounded border border-border bg-bg-2 p-3">
              <MarkdownView value={step.candidateValue || "No candidate text recorded."} />
            </div>
          </div>
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
              history at proposal time ({history.length} entries)
            </div>
            {history.length > 0 ? (
              <ul className="space-y-1.5">
                {history.map((item) => (
                  <li
                    key={`${item.iterIndex}-${item.stepIndex}`}
                    className="rounded border border-border bg-bg-2 px-2 py-1.5 text-[12px] text-muted"
                  >
                    <span className="font-mono text-text">{formatScore(item.score)}</span>
                    <span className="mx-2 text-muted-2">-</span>
                    <span>{shortText(item.candidateValue, 120)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="rounded border border-border bg-bg-2 px-2 py-2 text-[12px] text-muted-2">
                no earlier evaluated candidates in this session
              </div>
            )}
          </div>
        </div>

        <aside className="space-y-2 rounded border border-border bg-bg-2 p-3">
          <RunLink label="Open proposer invocation" run={step.proposerRun} />
          <RunLink label="Open evaluator invocation" run={step.evaluatorRun} />
          <div className="pt-1 text-[11px] text-muted">
            cost{" "}
            <span className="font-mono text-text">
              {formatCost(
                (step.proposerRun?.cost?.cost_usd ?? 0) + (step.evaluatorRun?.cost?.cost_usd ?? 0),
              )}
            </span>
          </div>
        </aside>
      </div>
    </section>
  );
}

function RunLink({ label, run }: { label: string; run: RunSummary | null }) {
  if (!run) {
    return (
      <div className="rounded border border-border px-2 py-1.5 text-[11px] text-muted-2">
        {label}: unavailable
      </div>
    );
  }
  return (
    <Link
      to={childHref(run)}
      className="block rounded border border-border bg-bg-1 px-2 py-1.5 text-[11px] text-text transition-colors hover:border-border-strong"
    >
      <span className="block">{label}</span>
      <span className="font-mono text-muted">{truncateMiddle(run.run_id, 18)}</span>
    </Link>
  );
}

export function buildOPROSteps(
  dataIterations: unknown,
  dataEvents: unknown,
  dataChildren?: unknown,
): OPROStep[] {
  const rows = eventEntries(dataEvents);
  if (rows.length === 0) rows.push(...iterationEntries(dataIterations));

  const byIter = new Map<number, Partial<OPROStep>>();
  for (const row of rows) {
    const current = byIter.get(row.iterIndex) ?? {};
    byIter.set(row.iterIndex, {
      ...current,
      iterIndex: row.iterIndex,
      stepIndex: row.stepIndex,
      paramPath: row.paramPath ?? current.paramPath ?? "-",
      currentValue: row.currentValue ?? current.currentValue ?? null,
      candidateValue: row.candidateValue ?? current.candidateValue ?? "",
      historySize: row.historySize ?? current.historySize ?? null,
      score: row.score ?? current.score ?? null,
      accepted: row.accepted ?? current.accepted ?? null,
      proposedAt: row.phase === "propose" ? row.timestamp : (current.proposedAt ?? null),
      evaluatedAt: row.phase === "evaluate" ? row.timestamp : (current.evaluatedAt ?? null),
    });
  }

  const children = parseChildren(dataChildren);
  const steps = [...byIter.values()]
    .map((item, index) => ({
      iterIndex: item.iterIndex ?? index,
      stepIndex: item.stepIndex ?? item.iterIndex ?? index,
      paramPath: item.paramPath ?? "-",
      currentValue: item.currentValue ?? null,
      candidateValue: item.candidateValue ?? "",
      historySize: item.historySize ?? null,
      score: item.score ?? null,
      accepted: item.accepted ?? null,
      proposedAt: item.proposedAt ?? null,
      evaluatedAt: item.evaluatedAt ?? null,
      proposerRun: null,
      evaluatorRun: null,
    }))
    .sort((a, b) => a.stepIndex - b.stepIndex || a.iterIndex - b.iterIndex);
  return steps.map((step, index) => ({
    ...step,
    proposerRun: children[index * 2] ?? null,
    evaluatorRun: children[index * 2 + 1] ?? null,
  }));
}

export function parseChildren(dataChildren: unknown): RunSummary[] {
  const raw = Array.isArray(dataChildren)
    ? dataChildren
    : isRecord(dataChildren) && Array.isArray(dataChildren.children)
      ? dataChildren.children
      : [];
  const parsed = z.array(RunSummarySchema).safeParse(raw);
  return parsed.success ? parsed.data.slice().sort((a, b) => a.started_at - b.started_at) : [];
}

export function childHref(run: RunSummary): string {
  if (isOPROAlgorithm(run.algorithm_path)) return `/opro/${encodeURIComponent(run.run_id)}`;
  if (run.algorithm_path === "Trainer" || run.algorithm_path?.endsWith(".Trainer")) {
    return `/training/${encodeURIComponent(run.run_id)}`;
  }
  if (run.is_algorithm) return `/algorithms/${encodeURIComponent(run.run_id)}`;
  const identity = run.hash_content ?? run.root_agent_path ?? run.run_id;
  return `/agents/${encodeURIComponent(identity)}/runs/${encodeURIComponent(run.run_id)}`;
}

export function shortText(value: string, max = 80): string {
  const trimmed = value.replace(/\s+/g, " ").trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 3)}...`;
}

type OPROEntry = {
  iterIndex: number;
  stepIndex: number;
  phase: string | null;
  paramPath: string | null;
  currentValue: string | null;
  candidateValue: string | null;
  historySize: number | null;
  score: number | null;
  accepted: boolean | null;
  timestamp: number | null;
};

function eventEntries(dataEvents: unknown): OPROEntry[] {
  const parsed = RunEventsResponse.safeParse(dataEvents);
  if (!parsed.success) return [];
  return parsed.data.events
    .filter((event): event is z.infer<typeof AlgoEventEnvelope> => event.type === "algo_event")
    .filter((event) => event.kind === "iteration" && isOPROAlgorithm(event.algorithm_path))
    .map((event) => entryFromPayload(event.payload, event.started_at));
}

export function isOPROAlgorithm(path: string | null | undefined): boolean {
  return path === "OPRO" || path === "OPROOptimizer";
}

function iterationEntries(dataIterations: unknown): OPROEntry[] {
  const parsed = IterationsResponse.safeParse(dataIterations);
  if (!parsed.success) return [];
  return parsed.data.iterations.map((iteration) =>
    entryFromPayload(
      { ...iteration.metadata, phase: iteration.phase, score: iteration.score },
      null,
      iteration.iter_index,
    ),
  );
}

function entryFromPayload(
  payload: Record<string, unknown>,
  timestamp: number | null,
  fallbackIter?: number,
): OPROEntry {
  const iterIndex = numberValue(payload.iter_index) ?? fallbackIter ?? 0;
  return {
    iterIndex,
    stepIndex: numberValue(payload.step_index) ?? iterIndex,
    phase: stringValue(payload.phase),
    paramPath: stringValue(payload.param_path),
    currentValue: stringValue(payload.current_value),
    candidateValue: stringValue(payload.candidate_value) ?? stringValue(payload.text),
    historySize: numberValue(payload.history_size),
    score: numberValue(payload.score),
    accepted: booleanValue(payload.accepted),
    timestamp,
  };
}

function parseStepParam(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "-";
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function booleanValue(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
