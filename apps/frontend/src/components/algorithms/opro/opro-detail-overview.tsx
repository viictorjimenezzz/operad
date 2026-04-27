import {
  type OPROStep,
  buildOPROSteps,
  childHref,
} from "@/components/algorithms/opro/opro-history-tab";
import { EmptyState, PanelCard, PanelGrid, Pill, StatusDot } from "@/components/ui";
import { MarkdownView } from "@/components/ui/markdown";
import { hashColor } from "@/lib/hash-color";
import { RunSummary as RunSummarySchema } from "@/lib/types";
import { formatCost, formatDurationMs, formatTokens } from "@/lib/utils";
import { Link } from "react-router-dom";

interface OPRODetailOverviewProps {
  summary?: unknown;
  iterations?: unknown;
  events?: unknown;
  dataChildren?: unknown;
  runId?: string;
}

export function OPRODetailOverview({
  summary,
  iterations,
  events,
  dataChildren,
  runId,
}: OPRODetailOverviewProps) {
  const parsed = RunSummarySchema.safeParse(summary);
  const run = parsed.success ? parsed.data : null;
  const steps = buildOPROSteps(iterations, events, dataChildren);
  const params = paramPaths(steps);
  const accepted = steps.filter((step) => step.accepted === true);
  const best = bestAcceptedStep(steps);
  const state = run?.state ?? "running";
  const statusTone = state === "error" ? "error" : state === "running" ? "live" : "ok";
  const totalCost = run?.cost?.cost_usd ?? 0;
  const totalTokens = (run?.prompt_tokens ?? 0) + (run?.completion_tokens ?? 0);

  if (!run && steps.length === 0) {
    return (
      <EmptyState
        title="OPRO data unavailable"
        description="the dashboard has not loaded this optimizer run yet"
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-bg-1 px-3 py-2 text-[12px] text-muted">
        <Pill tone={statusTone} pulse={state === "running"}>
          {state}
        </Pill>
        <StatusDot
          identity={run?.hash_content ?? runId ?? run?.run_id ?? "OPRO"}
          state={state === "running" ? "running" : state === "error" ? "error" : "ended"}
          size="sm"
        />
        <span>
          param{" "}
          <span className="font-mono text-text">{params.length > 0 ? params.join(", ") : "-"}</span>
        </span>
        <span>steps {steps.length}</span>
        <span>accepted {accepted.length}</span>
        <span>best {best?.score != null ? best.score.toFixed(3) : "-"}</span>
        <span>cost {formatCost(totalCost)}</span>
        <span>tokens {formatTokens(totalTokens)}</span>
        <span>wall {formatDurationMs(run?.duration_ms)}</span>
      </div>

      <PanelGrid cols={2} gap="md">
        <PanelCard title="score history" bodyMinHeight={280}>
          <OPROScoreChart
            steps={steps}
            identity={run?.hash_content ?? run?.run_id ?? runId ?? "OPRO"}
          />
        </PanelCard>
        <PanelCard title="headline candidate" bodyMinHeight={280}>
          {best ? (
            <div className="flex h-full flex-col gap-3">
              <div className="rounded border border-border bg-bg-2 p-3">
                <MarkdownView value={best.candidateValue || "No candidate text recorded."} />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
                <Pill tone="ok">accepted</Pill>
                <span>score {best.score?.toFixed(3) ?? "-"}</span>
                <span>step {best.stepIndex}</span>
              </div>
              {best.evaluatorRun ? (
                <Link
                  to={childHref(best.evaluatorRun)}
                  className="mt-auto inline-flex w-fit rounded border border-border bg-bg-2 px-2 py-1.5 text-[12px] text-text transition-colors hover:border-border-strong"
                >
                  Open evaluator run
                </Link>
              ) : null}
            </div>
          ) : (
            <EmptyState
              title="no accepted candidate"
              description="OPRO has not accepted a parameter rewrite in this session"
              className="min-h-48"
            />
          )}
        </PanelCard>
      </PanelGrid>

      {run?.parent_run_id ? (
        <PanelCard title="parent context">
          <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
            <span>
              This OPRO session ran inside Trainer run{" "}
              <span className="font-mono text-text">{run.parent_run_id}</span>.
            </span>
            {best ? <span>best candidate landed at optimizer step {best.stepIndex}.</span> : null}
            <Link
              to={`/training/${encodeURIComponent(run.parent_run_id)}`}
              className="rounded border border-border bg-bg-2 px-2 py-1 text-text transition-colors hover:border-border-strong"
            >
              Open Trainer run
            </Link>
          </div>
        </PanelCard>
      ) : null}
    </div>
  );
}

function OPROScoreChart({ steps, identity }: { steps: OPROStep[]; identity: string }) {
  const points = steps.filter((step) => step.score != null);
  if (points.length === 0) {
    return (
      <EmptyState title="no scores" description="evaluate events have not emitted scores yet" />
    );
  }

  const width = 640;
  const height = 250;
  const pad = { top: 18, right: 16, bottom: 28, left: 42 };
  const xs = points.map((point) => point.stepIndex);
  const ys = points.map((point) => point.score as number);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xSpan = Math.max(xMax - xMin, 1);
  const ySpan = Math.max(yMax - yMin, 1e-9);
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const xToPx = (x: number) => pad.left + ((x - xMin) / xSpan) * innerW;
  const yToPx = (y: number) => pad.top + (1 - (y - yMin) / ySpan) * innerH;
  const line = points
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${xToPx(point.stepIndex).toFixed(2)} ${yToPx(
          point.score as number,
        ).toFixed(2)}`,
    )
    .join(" ");
  const bestLine = bestSoFar(points)
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${xToPx(point.stepIndex).toFixed(2)} ${yToPx(
          point.best,
        ).toFixed(2)}`,
    )
    .join(" ");

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="OPRO score history"
      preserveAspectRatio="none"
    >
      <title>OPRO score history</title>
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
        const y = yMin + tick * ySpan;
        return (
          <g key={tick}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={yToPx(y)}
              y2={yToPx(y)}
              stroke="var(--color-border)"
              strokeDasharray="2 3"
              opacity={0.55}
            />
            <text
              x={pad.left - 6}
              y={yToPx(y)}
              fontSize={10}
              fill="var(--color-muted-2)"
              textAnchor="end"
              dominantBaseline="central"
            >
              {y.toFixed(2)}
            </text>
          </g>
        );
      })}
      <line
        x1={pad.left}
        x2={width - pad.right}
        y1={height - pad.bottom}
        y2={height - pad.bottom}
        stroke="var(--color-border)"
      />
      <path d={line} fill="none" stroke={hashColor(identity)} strokeWidth={1.5} />
      <path
        d={bestLine}
        fill="none"
        stroke="var(--color-ok)"
        strokeWidth={1.5}
        strokeDasharray="4 4"
      />
      {points.map((point) => {
        const accepted = point.accepted === true;
        return (
          <circle
            key={`${point.iterIndex}-${point.stepIndex}`}
            cx={xToPx(point.stepIndex)}
            cy={yToPx(point.score as number)}
            r={accepted ? 4 : 3.5}
            fill={accepted ? "var(--color-ok)" : "var(--color-bg-1)"}
            stroke={accepted ? "var(--color-ok)" : "var(--color-warn)"}
            strokeWidth={1.5}
          />
        );
      })}
      <text
        x={width - pad.right}
        y={height - 7}
        fontSize={10}
        fill="var(--color-muted-2)"
        textAnchor="end"
      >
        step
      </text>
      <text x={8} y={12} fontSize={10} fill="var(--color-muted-2)">
        score
      </text>
    </svg>
  );
}

function bestSoFar(points: OPROStep[]): Array<{ stepIndex: number; best: number }> {
  let best = Number.NEGATIVE_INFINITY;
  return points.map((point) => {
    if (point.score != null && point.score > best) best = point.score;
    return { stepIndex: point.stepIndex, best };
  });
}

function bestAcceptedStep(steps: OPROStep[]): OPROStep | null {
  const accepted = steps.filter((step) => step.accepted === true && step.score != null);
  if (accepted.length === 0) return null;
  return accepted.reduce((best, step) =>
    (step.score ?? Number.NEGATIVE_INFINITY) > (best.score ?? Number.NEGATIVE_INFINITY)
      ? step
      : best,
  );
}

function paramPaths(steps: OPROStep[]): string[] {
  return [...new Set(steps.map((step) => step.paramPath).filter((path) => path !== "-"))];
}
