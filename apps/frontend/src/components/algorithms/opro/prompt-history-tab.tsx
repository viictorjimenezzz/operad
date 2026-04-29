import { buildOPROSteps, shortText } from "@/components/algorithms/opro/opro-history-tab";
import { OPROScorePanel } from "@/components/algorithms/opro/score-curve-tab";
import { MarkdownView } from "@/components/ui";
import { EmptyState, Pill } from "@/components/ui";
import { useUrlState } from "@/hooks/use-url-state";
import { RunEventsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMemo } from "react";

export function OPROPromptHistoryTab({
  dataIterations,
  dataEvents,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
}) {
  const [stepParam, setStepParam] = useUrlState("step");
  const expandedStep = parseStepParam(stepParam);
  const initialPrompt = useMemo(() => initialPromptFromEvents(dataEvents), [dataEvents]);
  const steps = useMemo(
    () =>
      buildOPROSteps(dataIterations, dataEvents).filter(
        (step) => step.candidateValue.trim().length > 0,
      ),
    [dataEvents, dataIterations],
  );

  if (steps.length === 0) {
    return (
      <EmptyState
        title="no prompt history yet"
        description="OPRO prompt proposals appear after iteration events are emitted"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto max-w-[1280px] space-y-4">
        <section className="rounded border border-border bg-bg-1 p-3">
          <OPROScorePanel dataIterations={dataIterations} dataEvents={dataEvents} compact />
        </section>

        <ol className="relative flex flex-col gap-3 border-l border-border pl-5">
          {steps.map((step, index) => {
            const previous = steps[index - 1];
            const before = step.currentValue ?? previous?.candidateValue ?? initialPrompt ?? "";
            const beforeLabel = index === 0 ? "initial" : "previous";
            const expanded = expandedStep === step.stepIndex;
            return (
              <li key={`${step.iterIndex}-${step.stepIndex}`}>
                <section
                  className={cn(
                    "relative rounded border bg-bg-1",
                    expanded ? "border-accent ring-1 ring-[--color-accent-dim]" : "border-border",
                  )}
                >
                  <span className="absolute -left-[27px] top-3 h-3 w-3 rounded-full border border-border bg-bg-1" />
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 border-b border-border px-3 py-2 text-left transition-colors hover:bg-bg-2"
                    onClick={() => setStepParam(expanded ? null : String(step.stepIndex))}
                  >
                    <div className="min-w-0 text-[12px] text-text">
                      <div className="font-medium">iteration {step.stepIndex}</div>
                      <div className="truncate text-[11px] text-muted">
                        {step.paramPath} · score {formatScore(step.score)}
                      </div>
                    </div>
                    {step.accepted === true ? (
                      <Pill tone="ok">accepted</Pill>
                    ) : step.accepted === false ? (
                      <Pill tone="warn">rejected</Pill>
                    ) : (
                      <Pill tone="default">pending</Pill>
                    )}
                  </button>
                  <div className="p-3">
                    {expanded ? (
                      <ExpandedPromptPair
                        before={before}
                        beforeLabel={beforeLabel}
                        after={step.candidateValue}
                        afterLabel={`step ${step.stepIndex}`}
                      />
                    ) : (
                      <DiffPreview before={before} after={step.candidateValue} />
                    )}
                  </div>
                </section>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

function DiffPreview({ before, after }: { before: string; after: string }) {
  const beforeText = before.trim();
  const afterText = after.trim();
  return (
    <div className="space-y-2 rounded border border-border bg-bg-inset p-2 text-[12px]">
      <div className="rounded border border-[--color-err-dim] bg-[--color-err-dim]/30 px-2 py-1.5 text-[--color-err]">
        <span className="font-mono text-[10px] uppercase text-muted-2">- </span>
        {beforeText ? shortText(beforeText, 220) : "(no prior prompt)"}
      </div>
      <div className="rounded border border-[--color-ok-dim] bg-[--color-ok-dim]/30 px-2 py-1.5 text-[--color-ok]">
        <span className="font-mono text-[10px] uppercase text-muted-2">+ </span>
        {afterText ? shortText(afterText, 220) : "(no candidate prompt)"}
      </div>
    </div>
  );
}

function ExpandedPromptPair({
  before,
  beforeLabel,
  after,
  afterLabel,
}: {
  before: string;
  beforeLabel: string;
  after: string;
  afterLabel: string;
}) {
  return (
    <div className="space-y-3">
      <PromptPane label={beforeLabel} value={before || "No prior prompt recorded."} tone="before" />
      <PromptPane
        label={afterLabel}
        value={after || "No candidate prompt recorded."}
        tone="after"
      />
    </div>
  );
}

function PromptPane({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "before" | "after";
}) {
  return (
    <div
      className={cn(
        "rounded border bg-bg-2",
        tone === "before" ? "border-[--color-err-dim]" : "border-[--color-ok-dim]",
      )}
    >
      <div className="border-b border-border px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.06em] text-muted">
        {label}
      </div>
      <div className="max-h-72 overflow-auto p-3 text-[12px] leading-5">
        <MarkdownView value={value} />
      </div>
    </div>
  );
}

function initialPromptFromEvents(dataEvents: unknown): string | null {
  const parsed = RunEventsResponse.safeParse(dataEvents);
  if (!parsed.success) return null;
  for (const event of parsed.data.events) {
    if (event.type !== "agent_event") continue;
    const input = event.input;
    if (input === null || typeof input !== "object" || Array.isArray(input)) continue;
    const current = (input as Record<string, unknown>).current_value;
    if (typeof current === "string" && current.trim()) return current;
  }
  return null;
}

function parseStepParam(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatScore(value: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "-";
}
