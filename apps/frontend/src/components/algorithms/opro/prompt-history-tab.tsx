import { buildOPROSteps } from "@/components/algorithms/opro/opro-history-tab";
import { MultiPromptDiff } from "@/components/charts/multi-prompt-diff";
import { useParameterDrawer } from "@/components/agent-view/structure";
import { EmptyState, Pill } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useMemo } from "react";

export function OPROPromptHistoryTab({
  dataIterations,
  dataEvents,
}: {
  dataIterations?: unknown;
  dataEvents?: unknown;
}) {
  const drawer = useParameterDrawer();
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
      <ol className="relative flex flex-col gap-3 border-l border-border pl-5">
        {steps.map((step, index) => {
          const previous = steps[index - 1];
          const selected = drawer.paramPath === step.paramPath && drawer.stepIndex === index;
          return (
            <li key={`${step.iterIndex}-${step.stepIndex}`}>
              <section
                className={cn(
                  "relative rounded border bg-bg-1",
                  selected ? "border-accent ring-1 ring-[--color-accent-dim]" : "border-border",
                )}
              >
                <span className="absolute -left-[27px] top-3 h-3 w-3 rounded-full border border-border bg-bg-1" />
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 border-b border-border px-3 py-2 text-left transition-colors hover:bg-bg-2"
                  onClick={() => drawer.open(step.paramPath, index)}
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
                  <MultiPromptDiff
                    prompts={[
                      {
                        runId: `${step.paramPath}:${previous?.stepIndex ?? "initial"}`,
                        label: previous ? `step ${previous.stepIndex}` : "initial",
                        text: previous?.candidateValue ?? "",
                      },
                      {
                        runId: `${step.paramPath}:${step.stepIndex}`,
                        label: `step ${step.stepIndex}`,
                        text: step.candidateValue,
                      },
                    ]}
                  />
                </div>
              </section>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function formatScore(value: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "-";
}
