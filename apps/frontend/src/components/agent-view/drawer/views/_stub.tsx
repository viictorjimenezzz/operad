import { JsonView } from "@/components/ui/json-view";

interface StubViewProps {
  kind: string;
  payload: Record<string, unknown>;
}

export function StubView({ kind, payload }: StubViewProps) {
  return (
    <div className="space-y-2 p-3">
      <div className="text-xs text-muted">no renderer registered for {kind}</div>
      <JsonView value={payload} />
    </div>
  );
}
