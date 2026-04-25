import { EmptyState } from "@/shared/ui/empty-state";
import { JsonView } from "@/shared/ui/json-view";
import { useEventBufferStore } from "@/stores";

export function RawEnvelopePanel() {
  const latest = useEventBufferStore((s) => s.latestEnvelope);
  if (!latest) return <EmptyState title="no envelope yet" />;
  return <JsonView value={latest} />;
}
