import { EmptyState } from "@/components/ui/empty-state";
import { JsonView } from "@/components/ui/json-view";
import { useEventBufferStore } from "@/stores";

export function RawEnvelopePanel() {
  const latest = useEventBufferStore((s) => s.latestEnvelope);
  if (!latest) return <EmptyState title="no envelope yet" />;
  return <JsonView value={latest} />;
}
