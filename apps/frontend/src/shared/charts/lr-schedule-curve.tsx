import { EmptyState } from "@/shared/ui/empty-state";

// LR schedule events are not yet emitted by Trainer; this component is a
// placeholder until the runtime surfaces them.
export function LrScheduleCurve({ data: _data, height: _height = 220 }: { data: unknown; height?: number }) {
  return (
    <EmptyState
      title="no LR schedule data"
      description="Trainer does not yet emit LR schedule events"
    />
  );
}
