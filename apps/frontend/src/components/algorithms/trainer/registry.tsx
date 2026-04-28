import { ParameterEvolutionMultiples } from "@/components/algorithms/trainer/parameter-evolution-multiples";
import { TrainerDriftTab } from "@/components/algorithms/trainer/trainer-drift-tab";
import { TrainerLossTab } from "@/components/algorithms/trainer/trainer-loss-tab";
import { TrainerScheduleTab } from "@/components/algorithms/trainer/trainer-schedule-tab";
import { TrainerTracebackTab } from "@/components/algorithms/trainer/trainer-traceback-tab";
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
  TrainerLossTab: ({ element }) => {
    const p = element.props as {
      dataFitness?: unknown;
      dataCheckpoints?: unknown;
      dataSummary?: unknown;
    };
    return (
      <TrainerLossTab
        dataFitness={p.dataFitness}
        dataCheckpoints={p.dataCheckpoints}
        dataSummary={p.dataSummary}
      />
    );
  },
  TrainerScheduleTab: ({ element }) => {
    const p = element.props as { dataFitness?: unknown; dataCheckpoints?: unknown };
    return <TrainerScheduleTab dataFitness={p.dataFitness} dataCheckpoints={p.dataCheckpoints} />;
  },
  TrainerDriftTab: ({ element }) => {
    const p = element.props as { dataDrift?: unknown };
    return <TrainerDriftTab dataDrift={p.dataDrift} />;
  },
  TrainerTracebackTab: ({ element }) => {
    const p = element.props as { runId?: string; dataSummary?: unknown };
    return <TrainerTracebackTab runId={p.runId} dataSummary={p.dataSummary} />;
  },
  TrainingTracebackTab: ({ element }) => {
    const p = element.props as { runId?: string; dataSummary?: unknown };
    return (
      <TrainerTracebackTab
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
