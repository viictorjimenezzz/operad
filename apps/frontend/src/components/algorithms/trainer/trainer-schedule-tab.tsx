import { CheckpointTimeline } from "@/components/charts/checkpoint-timeline";
import { LrScheduleCurve } from "@/components/charts/lr-schedule-curve";
import { CheckpointEntry } from "@/lib/types";
import { PanelCard } from "@/components/ui";
import { z } from "zod";

interface TrainerScheduleTabProps {
  dataFitness?: unknown;
  dataCheckpoints?: unknown;
}

const CheckpointRows = z.array(CheckpointEntry);

export function TrainerScheduleTab({ dataFitness, dataCheckpoints }: TrainerScheduleTabProps) {
  const checkpoints = CheckpointRows.safeParse(dataCheckpoints).data ?? [];
  const best = checkpoints.find((entry) => entry.is_best) ?? null;

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-4">
        <PanelCard title="learning-rate schedule" bodyMinHeight={320}>
          <LrScheduleCurve data={dataFitness} height={280} />
        </PanelCard>
        <PanelCard title="checkpoints">
          {best ? (
            <div className="mb-2 flex items-center gap-1 text-xs text-muted">
              <span className="text-sm leading-none text-[--color-warn]">★</span>
              <span>best epoch {best.epoch}</span>
            </div>
          ) : null}
          <CheckpointTimeline data={dataCheckpoints} />
        </PanelCard>
      </div>
    </div>
  );
}
