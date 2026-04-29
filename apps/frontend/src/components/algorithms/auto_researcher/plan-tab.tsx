import {
  buildAutoResearcherAttempts,
  readTerminalScore,
  selectBestAttempt,
} from "@/components/algorithms/auto_researcher/events";
import { PlanCard } from "@/components/algorithms/auto_researcher/plan-card";
import { EmptyState, Metric, Pill } from "@/components/ui";
import { RunSummary as RunSummarySchema } from "@/lib/types";
import { formatDurationMs, formatRelativeTime } from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import { useMemo } from "react";

export function AutoResearcherPlanTab({
  dataSummary,
  dataIterations,
  dataEvents,
  dataLangfuseUrl,
}: {
  dataSummary?: unknown;
  dataIterations?: unknown;
  dataEvents?: unknown;
  dataLangfuseUrl?: unknown;
}) {
  const attempts = useMemo(
    () => buildAutoResearcherAttempts(dataEvents, dataIterations),
    [dataEvents, dataIterations],
  );
  const plans = attempts.filter((attempt) => attempt.plan != null);
  const langfuseUrl = typeof dataLangfuseUrl === "string" ? dataLangfuseUrl : "";

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      {plans.length > 0 ? (
        plans.map((attempt, index) => (
          <PlanCard
            key={`${attempt.attemptIndex ?? "unknown"}-${index}`}
            attemptIndex={attempt.attemptIndex}
            plan={attempt.plan}
            evidence={attempt.evidence}
          />
        ))
      ) : (
        <EmptyState
          title="plans not available"
          description="no AutoResearcher plan event has been emitted for this run yet"
          className="min-h-40 rounded-lg border border-border bg-bg-1"
        />
      )}
      <RunDetailsStrip dataSummary={dataSummary} attempts={attempts} langfuseUrl={langfuseUrl} />
    </div>
  );
}

function RunDetailsStrip({
  dataSummary,
  attempts,
  langfuseUrl,
}: {
  dataSummary?: unknown;
  attempts: ReturnType<typeof buildAutoResearcherAttempts>;
  langfuseUrl: string;
}) {
  const parsed = RunSummarySchema.safeParse(dataSummary);
  if (!parsed.success) return null;

  const run = parsed.data;
  const terminalScore = readTerminalScore(run);
  const best = selectBestAttempt(attempts, terminalScore);
  const count = attemptCount(attempts);

  return (
    <section className="rounded-lg border border-border bg-bg-1 px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Pill
          tone={run.state === "running" ? "live" : run.state === "error" ? "error" : "ok"}
          pulse={run.state === "running"}
        >
          {run.state === "running" ? "running" : run.state === "error" ? "error" : "ended"}
        </Pill>
        <Pill tone="algo">algo</Pill>
        <Metric label="ago" value={formatRelativeTime(run.started_at)} />
        <Metric label="dur" value={formatDurationMs(run.duration_ms)} />
        <Metric label="attempts" value={count} />
        <Metric label="best" value={formatScore(terminalScore ?? best?.bestScore ?? null)} />
        <Metric label="events" value={run.event_total} />
        {langfuseUrl ? (
          <a
            href={langfuseUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[12px] text-accent transition-colors hover:text-accent-strong"
            title="Open in Langfuse"
          >
            langfuse
            <ExternalLink size={11} />
          </a>
        ) : null}
      </div>
    </section>
  );
}

function attemptCount(attempts: ReturnType<typeof buildAutoResearcherAttempts>): string {
  const indexed = attempts.filter((attempt) => attempt.attemptIndex != null).length;
  const count = indexed > 0 ? indexed : attempts.length;
  return count > 0 ? String(count) : "n/a";
}

function formatScore(value: number | null): string {
  return typeof value === "number" ? value.toFixed(3) : "n/a";
}
