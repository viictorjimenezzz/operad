import type { DrawerKind, DrawerPayload } from "@/stores/ui";

export function DrawerStub({
  kind,
  payload,
  runId,
}: {
  kind: Exclude<DrawerKind, null>;
  payload: DrawerPayload;
  runId: string;
}) {
  return (
    <div className="h-full overflow-auto p-3">
      <div className="mb-2 text-[11px] uppercase tracking-[0.08em] text-muted">stub view</div>
      <pre className="overflow-auto rounded-md border border-border bg-bg-2 p-3 text-[11px]">
        {JSON.stringify({ kind, runId, payload }, null, 2)}
      </pre>
    </div>
  );
}
