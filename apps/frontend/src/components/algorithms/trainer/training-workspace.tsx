import { ParameterEvolutionMultiples } from "@/components/algorithms/trainer/parameter-evolution-multiples";
import { CheckpointTimeline } from "@/components/charts/checkpoint-timeline";
import { DriftTimeline } from "@/components/charts/drift-timeline";
import { GradientLog } from "@/components/charts/gradient-log";
import { LrScheduleCurve } from "@/components/charts/lr-schedule-curve";
import { TrainingLossCurve } from "@/components/charts/training-loss-curve";
import { TrainingProgress } from "@/components/charts/training-progress";
import { EmptyState, Metric, PanelCard, PanelGrid, PanelGridItem, Pill } from "@/components/ui";
import { AlgoEventEnvelope, GradientEntry, ProgressSnapshot } from "@/lib/types";
import { formatDurationMs, formatNumber } from "@/lib/utils";
import { Fragment, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

interface TrainingWorkspaceProps {
  dataFitness?: unknown;
  dataCheckpoints?: unknown;
  dataDrift?: unknown;
  dataGradients?: unknown;
  dataProgress?: unknown;
  dataSummary?: unknown;
  dataEvents?: unknown;
  runId?: string;
}

const GradientRows = z.array(GradientEntry);
export function TrainingWorkspace({
  dataFitness,
  dataCheckpoints,
  dataDrift,
  dataGradients,
  dataSummary,
}: TrainingWorkspaceProps) {
  const latestGradients = useMemo(() => latestGradientRows(dataGradients, 5), [dataGradients]);

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-3">
        <StudioBadge dataSummary={dataSummary} />
        <PanelGrid cols={2}>
          <PanelCard title="Loss curve" toolbar={<ViewFull tab="loss" />} bodyMinHeight={238}>
            <TrainingLossCurve data={dataFitness} checkpointData={dataCheckpoints} height={218} />
          </PanelCard>
          <PanelCard title="LR schedule" toolbar={<ViewFull tab="loss" />} bodyMinHeight={238}>
            <LrScheduleCurve data={dataFitness} height={218} />
          </PanelCard>
          <PanelCard
            title="Gradient log"
            toolbar={<ViewFull tab="gradients" />}
            bodyMinHeight={238}
          >
            <GradientLog data={latestGradients} />
          </PanelCard>
          <PanelCard
            title="Checkpoint timeline"
            toolbar={<ViewFull tab="checkpoints" />}
            bodyMinHeight={238}
          >
            <CheckpointTimeline data={dataCheckpoints} />
          </PanelCard>
          <PanelGridItem colSpan={2}>
            <PanelCard title="PromptDrift timeline" toolbar={<ViewFull tab="drift" />}>
              <DriftTimeline data={dataDrift} />
            </PanelCard>
          </PanelGridItem>
          <PanelGridItem colSpan={2}>
            <PanelCard title="Parameter evolution" toolbar={<ViewFull tab="parameters" />}>
              <ParameterEvolutionMultiples
                dataCheckpoints={dataCheckpoints}
                dataSummary={dataSummary}
                compact
              />
            </PanelCard>
          </PanelGridItem>
        </PanelGrid>
      </div>
    </div>
  );
}

export function TrainingProgressPanel({
  dataProgress,
  dataEvents,
}: {
  dataProgress?: unknown;
  dataEvents?: unknown;
}) {
  const parsed = ProgressSnapshot.safeParse(dataProgress);
  const cells = useMemo(() => batchCells(dataEvents), [dataEvents]);

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-4">
        <PanelCard title="ETA">
          {parsed.success ? (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <Metric
                label="eta"
                value={parsed.data.eta_s == null ? "-" : formatDurationMs(parsed.data.eta_s * 1000)}
              />
              <Metric label="elapsed" value={formatDurationMs(parsed.data.elapsed_s * 1000)} />
              <Metric label="rate" value={`${formatNumber(parsed.data.rate_batches_per_s)} b/s`} />
              <Metric
                label="epoch"
                value={
                  parsed.data.epochs_total
                    ? `${parsed.data.epoch} / ${parsed.data.epochs_total}`
                    : parsed.data.epoch
                }
              />
            </div>
          ) : (
            <EmptyState title="no training in progress" />
          )}
        </PanelCard>
        <PanelCard title="Training progress">
          <TrainingProgress data={dataProgress} />
        </PanelCard>
        <PanelCard title="Batch loss matrix">
          <BatchMatrix cells={cells} />
        </PanelCard>
      </div>
    </div>
  );
}

function ViewFull({ tab }: { tab: string }) {
  const [, setSearchParams] = useSearchParams();
  return (
    <button
      type="button"
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
      className="rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted transition-colors hover:border-border-strong hover:text-text"
    >
      View full
    </button>
  );
}

function StudioBadge({ dataSummary }: { dataSummary?: unknown }) {
  const summary = asRecord(dataSummary);
  const url = stringField(summary, ["studio_url", "studioUrl", "feedback_url", "feedbackUrl"]);
  const path = stringField(summary, ["feedback_path", "feedbackPath", "human_feedback_path"]);
  if (!url && !path) return null;

  return (
    <PanelCard>
      <div className="flex flex-wrap items-center gap-3 text-[12px] text-muted">
        <Pill tone="accent">Studio</Pill>
        <span>human feedback attached</span>
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent transition-colors hover:text-[--color-accent-strong]"
          >
            Open in Studio
          </a>
        ) : (
          <button
            type="button"
            disabled
            title={path ? `feedback rows: ${path}` : "Studio link unavailable"}
            className="rounded border border-border px-2 py-1 text-[11px] text-muted opacity-70"
          >
            Open in Studio
          </button>
        )}
      </div>
    </PanelCard>
  );
}

function latestGradientRows(data: unknown, limit: number) {
  const parsed = GradientRows.safeParse(data);
  if (!parsed.success) return [];
  return [...parsed.data].sort((a, b) => b.epoch - a.epoch || b.batch - a.batch).slice(0, limit);
}

type BatchCell = { epoch: number; batch: number; loss: number };

function batchCells(data: unknown): BatchCell[] {
  const events: Array<z.infer<typeof AlgoEventEnvelope>> = [];
  if (Array.isArray(data)) {
    for (const event of data) {
      const parsed = AlgoEventEnvelope.safeParse(event);
      if (parsed.success) events.push(parsed.data);
    }
  }
  return events
    .filter((event) => event.algorithm_path === "Trainer" && event.kind === "batch_end")
    .map((event) => {
      const payload = event.payload;
      const epoch = payload.epoch;
      const batch = payload.batch;
      const trainLoss = payload.train_loss;
      if (typeof epoch !== "number" || typeof batch !== "number" || typeof trainLoss !== "number") {
        return null;
      }
      return { epoch, batch, loss: trainLoss };
    })
    .filter((cell): cell is BatchCell => cell != null);
}

function BatchMatrix({ cells }: { cells: BatchCell[] }) {
  if (cells.length === 0) {
    return (
      <EmptyState
        title="no batch loss matrix"
        description="batch_end events have not emitted train_loss yet"
      />
    );
  }
  const epochs = [...new Set(cells.map((cell) => cell.epoch))].sort((a, b) => a - b);
  const batches = [...new Set(cells.map((cell) => cell.batch))].sort((a, b) => a - b);
  const min = Math.min(...cells.map((cell) => cell.loss));
  const max = Math.max(...cells.map((cell) => cell.loss));
  const byKey = new Map(cells.map((cell) => [`${cell.epoch}:${cell.batch}`, cell]));

  return (
    <div className="overflow-auto">
      <div
        className="grid min-w-[520px] gap-1 text-[10px]"
        style={{
          gridTemplateColumns: `64px repeat(${batches.length}, minmax(12px, 1fr))`,
        }}
      >
        <span />
        {batches.map((batch) => (
          <span key={batch} className="truncate text-center font-mono text-muted-2">
            {batch}
          </span>
        ))}
        {epochs.map((epoch) => (
          <Fragment key={epoch}>
            <span key={`label-${epoch}`} className="font-mono text-muted">
              epoch {epoch}
            </span>
            {batches.map((batch) => {
              const cell = byKey.get(`${epoch}:${batch}`);
              return (
                <span
                  key={`${epoch}:${batch}`}
                  className="h-4 rounded border border-border"
                  title={
                    cell
                      ? `epoch ${epoch}, batch ${batch}, loss ${formatNumber(cell.loss)}`
                      : `epoch ${epoch}, batch ${batch}`
                  }
                  style={{
                    background: cell ? `var(--qual-${lossBucket(cell.loss, min, max)})` : "none",
                  }}
                />
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function lossBucket(value: number, min: number, max: number): number {
  if (max <= min) return 7;
  const ratio = Math.max(0, Math.min(1, (value - min) / (max - min)));
  return Math.max(1, Math.min(12, Math.round(ratio * 11) + 1));
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringField(value: Record<string, unknown> | null, keys: string[]): string | null {
  if (!value) return null;
  for (const key of keys) {
    const next = value[key];
    if (typeof next === "string" && next.length > 0) return next;
  }
  return null;
}
