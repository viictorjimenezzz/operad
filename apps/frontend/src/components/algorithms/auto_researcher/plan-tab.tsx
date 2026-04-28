import { EmptyState } from "@/components/ui/empty-state";

interface PlanStep {
  text: string;
  status: "planned" | "in-progress" | "done";
}

export function AutoResearcherPlanTab({ dataEvents }: { dataEvents?: unknown }) {
  const plan = firstPlanPayload(parseEvents(dataEvents));
  const steps = buildPlanSteps(plan);

  if (steps.length === 0) {
    return (
      <EmptyState
        title="plan steps unavailable"
        description="no plan event has been emitted for this run yet"
      />
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <section className="rounded-lg border border-border bg-bg-1">
        <header className="border-b border-border px-4 py-3">
          <h2 className="m-0 text-[14px] font-semibold text-text">Research plan</h2>
          <p className="m-0 mt-1 text-[11px] text-muted">
            Planner steps from the first plan event in this run.
          </p>
        </header>
        <ol className="m-0 list-decimal space-y-2 px-8 py-4 text-[12px] text-text">
          {steps.map((step, index) => (
            <li key={`${index}-${step.text}`} className="leading-5">
              <span className="inline-flex items-center gap-2">
                <StepStatus status={step.status} />
                <span>{step.text}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function StepStatus({ status }: { status: PlanStep["status"] }) {
  if (status === "done") {
    return <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--color-ok)]" aria-label="done" />;
  }
  if (status === "in-progress") {
    return (
      <span
        className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--color-warn)]"
        aria-label="in-progress"
      />
    );
  }
  return <span className="inline-block h-2.5 w-2.5 rounded-full bg-muted" aria-label="planned" />;
}

function parseEvents(data: unknown): unknown[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).events)) {
    return (data as Record<string, unknown>).events as unknown[];
  }
  return [];
}

function firstPlanPayload(events: unknown[]): unknown {
  for (const event of events) {
    if (!event || typeof event !== "object") continue;
    const record = event as Record<string, unknown>;
    if (record.type !== "algo_event") continue;
    const kind = record.kind;
    const payload =
      record.payload && typeof record.payload === "object"
        ? (record.payload as Record<string, unknown>)
        : null;
    if (!payload) continue;
    if (kind === "plan") return payload.plan ?? payload;
    if (kind === "iteration" && payload.phase === "plan") return payload.plan ?? payload;
  }
  return null;
}

function buildPlanSteps(plan: unknown): PlanStep[] {
  if (plan == null) return [];

  if (typeof plan === "string") {
    return [{ text: plan, status: "planned" }];
  }

  if (Array.isArray(plan)) {
    return plan
      .map((item) => toPlanStep(item))
      .filter((item): item is PlanStep => item !== null);
  }

  if (typeof plan !== "object") {
    return [{ text: String(plan), status: "planned" }];
  }

  const record = plan as Record<string, unknown>;
  const structured = record.steps ?? record.plan ?? record.items;
  if (Array.isArray(structured)) {
    const steps = structured
      .map((item) => toPlanStep(item))
      .filter((item): item is PlanStep => item !== null);
    if (steps.length > 0) return steps;
  }

  return Object.entries(record)
    .filter(([key]) => key !== "status")
    .map(([key, value]) => ({
      text: `${key}: ${formatValue(value)}`,
      status: "planned" as const,
    }));
}

function toPlanStep(value: unknown): PlanStep | null {
  if (typeof value === "string") {
    return { text: value, status: "planned" };
  }
  if (!value || typeof value !== "object") {
    return value == null ? null : { text: String(value), status: "planned" };
  }

  const record = value as Record<string, unknown>;
  const textValue = record.text ?? record.step ?? record.title ?? record.query ?? record.description;
  const text = textValue == null ? null : String(textValue);
  if (!text) return null;
  return {
    text,
    status: parseStatus(record.status ?? record.state ?? record.phase),
  };
}

function parseStatus(raw: unknown): PlanStep["status"] {
  const value = typeof raw === "string" ? raw.toLowerCase() : "";
  if (value === "done" || value === "complete" || value === "completed") return "done";
  if (value === "in-progress" || value === "running" || value === "active") return "in-progress";
  return "planned";
}

function formatValue(value: unknown): string {
  if (value == null) return "n/a";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
