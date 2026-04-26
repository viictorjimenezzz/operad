import { ChangeRow } from "@/components/agent-view/drawer/views/diff/change-row";
import { EmptyState } from "@/components/ui/empty-state";
import { dashboardApi } from "@/lib/api/dashboard";
import type { DrawerPayload } from "@/stores/ui";
import { useQuery } from "@tanstack/react-query";

interface InvocationDiffViewProps {
  runId: string;
  payload: DrawerPayload;
}

export function InvocationDiffView({ runId, payload }: InvocationDiffViewProps) {
  const agentPath = typeof payload.agentPath === "string" ? payload.agentPath : null;
  const fromInvocationId =
    typeof payload.fromInvocationId === "string" ? payload.fromInvocationId : null;
  const toInvocationId =
    typeof payload.toInvocationId === "string" ? payload.toInvocationId : null;

  const query = useQuery({
    queryKey: ["run", "agent-diff", runId, agentPath, fromInvocationId, toInvocationId] as const,
    queryFn: () => {
      if (!runId) throw new Error("runId is required");
      if (!agentPath) throw new Error("agentPath is required");
      if (!fromInvocationId || !toInvocationId) throw new Error("from/to invocation ids are required");
      return dashboardApi.agentDiff(runId, agentPath, fromInvocationId, toInvocationId);
    },
    enabled: !!runId && !!agentPath && !!fromInvocationId && !!toInvocationId,
  });

  if (!agentPath || !fromInvocationId || !toInvocationId) {
    return <EmptyState title="missing diff payload" description="agentPath/fromInvocationId/toInvocationId are required" />;
  }
  if (query.isPending) {
    return <div className="p-3 text-xs text-muted">loading invocation diff…</div>;
  }
  if (query.isError || !query.data) {
    return <EmptyState title="failed to load diff" description="check backend logs for /agent/{path}/diff" />;
  }

  const diff = query.data;
  return (
    <div className="space-y-3 p-3">
      <div className="rounded border border-border bg-bg-2 p-2 text-xs">
        <div className="mb-1 text-[11px] text-muted">
          {diff.from_invocation} -&gt; {diff.to_invocation}
        </div>
        <div className="grid grid-cols-[120px_1fr] gap-1 text-[11px]">
          <span className="text-muted">hash (from)</span>
          <code className="truncate text-text">{diff.from_hash_content ?? "-"}</code>
          <span className="text-muted">hash (to)</span>
          <code className="truncate text-text">{diff.to_hash_content ?? "-"}</code>
        </div>
      </div>

      {diff.changes.length === 0 ? (
        <EmptyState title="no state changes" description="these invocations have identical state snapshots" />
      ) : (
        <div className="space-y-2">
          {diff.changes.map((change, idx) => (
            <ChangeRow key={`${change.path}:${change.kind}:${idx}`} change={change} />
          ))}
        </div>
      )}
    </div>
  );
}
