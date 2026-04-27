import { ParameterEvolutionMultiples } from "@/components/algorithms/trainer/parameter-evolution-multiples";
import {
  TrainingProgressPanel,
  TrainingWorkspace,
} from "@/components/algorithms/trainer/training-workspace";
import { CheckpointTimeline } from "@/components/charts/checkpoint-timeline";
import { DriftTimeline } from "@/components/charts/drift-timeline";
import { GradientLog } from "@/components/charts/gradient-log";
import { LrScheduleCurve } from "@/components/charts/lr-schedule-curve";
import { TrainingLossCurve } from "@/components/charts/training-loss-curve";
import { TrainingProgress } from "@/components/charts/training-progress";
import { TrainingTracebackTab } from "@/dashboard/pages/run-detail/TrainingTracebackTab";
import type { ComponentRegistry } from "@json-render/react";

export const trainerRegistry: ComponentRegistry = {
  TrainingWorkspace: ({ element }) => {
    const p = element.props as {
      dataFitness?: unknown;
      dataCheckpoints?: unknown;
      dataDrift?: unknown;
      dataGradients?: unknown;
      dataProgress?: unknown;
      dataSummary?: unknown;
      runId?: string;
    };
    return <TrainingWorkspace {...p} />;
  },
  ParameterEvolutionMultiples: ({ element }) => {
    const p = element.props as {
      dataCheckpoints?: unknown;
      dataSummary?: unknown;
      compact?: boolean;
    };
    return <ParameterEvolutionMultiples {...p} />;
  },
  TrainingProgressPanel: ({ element }) => {
    const p = element.props as { dataProgress?: unknown; dataEvents?: unknown };
    return <TrainingProgressPanel {...p} />;
  },
  TrainingTracebackTab: ({ element }) => {
    const p = element.props as { runId?: string; dataSummary?: unknown };
    return (
      <TrainingTracebackTab
        {...(p.runId !== undefined ? { runId: p.runId } : {})}
        dataSummary={p.dataSummary}
      />
    );
  },
  TrainingProgress: ({ element }) => (
    <TrainingProgress data={(element.props as { data?: unknown }).data} />
  ),
  TrainingLossCurve: ({ element }) => {
    const p = element.props as { data?: unknown; dataCheckpoint?: unknown; height?: number };
    return (
      <TrainingLossCurve data={p.data} checkpointData={p.dataCheckpoint} height={p.height ?? 220} />
    );
  },
  LrScheduleCurve: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <LrScheduleCurve data={p.data} height={p.height ?? 220} />;
  },
  CheckpointTimeline: ({ element }) => (
    <CheckpointTimeline data={(element.props as { data?: unknown }).data} />
  ),
  DriftTimeline: ({ element }) => (
    <DriftTimeline data={(element.props as { data?: unknown }).data} />
  ),
  GradientLog: ({ element }) => <GradientLog data={(element.props as { data?: unknown }).data} />,
};
