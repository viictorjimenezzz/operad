import { EmptyState, MarkdownView, Metric } from "@/components/ui";
import { langfuseLinkProps } from "@/lib/langfuse";
import {
  cn,
  formatDurationMs,
  formatNumber,
  formatRelativeTime,
  truncateMiddle,
} from "@/lib/utils";

export type ParameterEvolutionPoint = {
  runId: string;
  startedAt: number;
  value: unknown;
  hash: string;
  gradient?: TextualGradient | null;
  sourceTapeStep?: TapeStepRef | null;
  langfuseUrl?: string | null;
  metricSnapshot?: Record<string, number>;
  latencyMs?: number | null;
};

export type TextualGradient = {
  message: string;
  severity: "low" | "medium" | "high";
  targetPaths: string[];
  critic?: {
    agentPath: string;
    runId: string;
    langfuseUrl?: string | null;
  };
};

export type TapeStepRef = {
  epoch: number;
  batch: number;
  iter: number;
  optimizerStep: number;
};

export interface WhyPaneProps {
  point: ParameterEvolutionPoint | null;
  previous?: ParameterEvolutionPoint | null;
  langfuseUrl?: string | null;
}

export function WhyPane({ point, previous, langfuseUrl }: WhyPaneProps) {
  if (!point) {
    return (
      <EmptyState
        title="select a step"
        description="Select a step in the timeline above to see how it changed."
      />
    );
  }

  return (
    <div className="space-y-3 border-t border-border p-3">
      <Header point={point} langfuseUrl={langfuseUrl ?? null} />
      {point.gradient ? (
        <GradientCard gradient={point.gradient} />
      ) : (
        <EmptyState
          title="no textual-gradient critic"
          description="This step's value was set without a textual-gradient critic, such as an initial value or hand-edit."
          className="min-h-24 rounded border border-border bg-bg-1"
        />
      )}
      {point.sourceTapeStep ? <TapeStepCard step={point.sourceTapeStep} /> : null}
      {point.metricSnapshot ? <MetricsRow metrics={point.metricSnapshot} /> : null}
      <Footer point={point} previous={previous ?? null} />
    </div>
  );
}

function Header({
  point,
  langfuseUrl,
}: {
  point: ParameterEvolutionPoint;
  langfuseUrl?: string | null;
}) {
  const directLink =
    point.langfuseUrl != null
      ? {
          href: point.langfuseUrl,
          target: "_blank" as const,
          rel: "noopener noreferrer" as const,
          title: "Open trace in Langfuse",
        }
      : null;
  const fallbackLink = langfuseLinkProps(langfuseUrl, point.runId);
  const link = directLink ?? fallbackLink;

  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
      <span className="font-medium text-text">step {stepLabel(point)}</span>
      <span className="font-mono">{truncateMiddle(point.runId, 18)}</span>
      <span>{formatRelativeTime(point.startedAt)}</span>
      {link ? (
        <a
          href={link.href}
          target={link.target}
          rel={link.rel}
          title={link.title}
          className="text-accent underline-offset-2 hover:underline"
        >
          langfuse -&gt;
        </a>
      ) : null}
    </div>
  );
}

function GradientCard({ gradient }: { gradient: TextualGradient }) {
  return (
    <section className="space-y-2 border-b border-border pb-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
          gradient
        </span>
        <SeverityChip severity={gradient.severity} />
      </div>
      <MarkdownView value={gradient.message || "No gradient message."} />
      {gradient.targetPaths.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {gradient.targetPaths.map((path) => (
            <span
              key={path}
              className="rounded border border-border bg-bg-2 px-1.5 py-0.5 font-mono text-[10px] text-muted"
            >
              {path}
            </span>
          ))}
        </div>
      ) : null}
      {gradient.critic?.langfuseUrl ? (
        <a
          href={gradient.critic.langfuseUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex text-[12px] text-accent underline-offset-2 hover:underline"
        >
          Open critic invocation in Langfuse -&gt;
        </a>
      ) : null}
    </section>
  );
}

function SeverityChip({ severity }: { severity: TextualGradient["severity"] }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em]",
        severity === "low" && "border-ok bg-ok-dim text-[--color-ok]",
        severity === "medium" && "border-warn bg-bg-3 text-warn",
        severity === "high" && "border-err bg-err-dim text-[--color-err]",
      )}
    >
      {severity}
    </span>
  );
}

function TapeStepCard({ step }: { step: TapeStepRef }) {
  return (
    <section className="flex flex-wrap gap-x-4 gap-y-2 border-b border-border pb-3">
      <Metric label="epoch" value={step.epoch} />
      <Metric label="batch" value={step.batch} />
      <Metric label="iter" value={step.iter} />
      <Metric label="optimizer_step" value={step.optimizerStep} />
    </section>
  );
}

function MetricsRow({ metrics }: { metrics: Record<string, number> }) {
  const entries = Object.entries(metrics).sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) return null;

  return (
    <section className="flex flex-wrap gap-x-4 gap-y-2 border-b border-border pb-3">
      {entries.map(([name, value]) => (
        <Metric key={name} label={name} value={formatNumber(value)} />
      ))}
    </section>
  );
}

function Footer({
  point,
  previous,
}: {
  point: ParameterEvolutionPoint;
  previous?: ParameterEvolutionPoint | null;
}) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2 text-[12px]">
      <Metric label="hash delta" value={formatHashDelta(point, previous)} />
      <Metric label="value delta" value={formatValueDelta(point.value, previous?.value)} />
      {previous?.latencyMs != null && point.latencyMs != null ? (
        <Metric
          label="latency delta"
          value={formatDurationDelta(point.latencyMs - previous.latencyMs)}
        />
      ) : null}
    </div>
  );
}

function stepLabel(point: ParameterEvolutionPoint): string {
  if (point.sourceTapeStep) return `#${point.sourceTapeStep.optimizerStep}`;
  return "#-";
}

function formatHashDelta(
  point: ParameterEvolutionPoint,
  previous?: ParameterEvolutionPoint | null,
): string {
  const current = truncateMiddle(point.hash, 12);
  if (!previous) return current;
  return `${truncateMiddle(previous.hash, 12)} -> ${current}`;
}

function formatValueDelta(current: unknown, previous: unknown): string {
  if (previous === undefined) return "baseline";
  if (typeof current === "number" && typeof previous === "number") {
    const delta = current - previous;
    return `${delta >= 0 ? "+" : ""}${formatNumber(delta)}`;
  }
  if (typeof current === "string" && typeof previous === "string") {
    const changed = changedWordCount(previous, current);
    return `${changed} changed word${changed === 1 ? "" : "s"}`;
  }
  return JSON.stringify(current) === JSON.stringify(previous) ? "unchanged" : "changed";
}

function changedWordCount(before: string, after: string): number {
  const a = before.trim().split(/\s+/).filter(Boolean);
  const b = after.trim().split(/\s+/).filter(Boolean);
  const length = Math.max(a.length, b.length);
  let changed = 0;
  for (let index = 0; index < length; index += 1) {
    if (a[index] !== b[index]) changed += 1;
  }
  return changed;
}

function formatDurationDelta(ms: number): string {
  const sign = ms >= 0 ? "+" : "-";
  return `${sign}${formatDurationMs(Math.abs(ms))}`;
}
