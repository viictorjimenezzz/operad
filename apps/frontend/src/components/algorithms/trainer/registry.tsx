import { CheckpointTimeline } from "@/components/charts/checkpoint-timeline";
import { DriftTimeline } from "@/components/charts/drift-timeline";
import { LrScheduleCurve } from "@/components/charts/lr-schedule-curve";
import { TrainingLossCurve } from "@/components/charts/training-loss-curve";
import { TrainingProgress } from "@/components/charts/training-progress";
import type { ComponentRegistry } from "@json-render/react";

export const trainerRegistry: ComponentRegistry = {
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
};
