import { DriftTimeline } from "@/components/charts/drift-timeline";
import { EmptyState, PanelCard } from "@/components/ui";
import { DriftEntry } from "@/lib/types";
import { useMemo, useState } from "react";
import { z } from "zod";

interface TrainerDriftTabProps {
  dataDrift?: unknown;
}

const DriftRows = z.array(DriftEntry);

export function TrainerDriftTab({ dataDrift }: TrainerDriftTabProps) {
  const entries = useMemo(() => {
    const parsed = DriftRows.safeParse(dataDrift);
    if (!parsed.success) return [];
    return [...parsed.data].sort((a, b) => a.epoch - b.epoch);
  }, [dataDrift]);

  const [selectedEpoch, setSelectedEpoch] = useState<number | null>(null);
  const active =
    entries.find((entry) => entry.epoch === selectedEpoch) ?? entries[entries.length - 1] ?? null;

  if (!active) {
    return (
      <div className="h-full overflow-auto p-4">
        <EmptyState title="no drift events" description="PromptDrift callback hasn't fired" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="space-y-4">
        <PanelCard title="drift events">
          <div className="flex flex-wrap gap-2">
            {entries.map((entry) => {
              const activeEpoch = entry.epoch === active.epoch;
              return (
                <button
                  key={entry.epoch}
                  type="button"
                  onClick={() => setSelectedEpoch(entry.epoch)}
                  className={
                    activeEpoch
                      ? "rounded border border-accent bg-bg-3 px-2 py-1 text-[11px] text-accent"
                      : "rounded border border-border bg-bg-2 px-2 py-1 text-[11px] text-muted"
                  }
                >
                  epoch {entry.epoch}
                </button>
              );
            })}
          </div>
        </PanelCard>

        <PanelCard title={`drift epoch ${active.epoch}`}>
          <DriftTimeline data={[active]} />
        </PanelCard>
      </div>
    </div>
  );
}
