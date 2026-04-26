import { InvocationsList } from "@/components/agent-view/overview/invocations-list";
import { dashboardApi } from "@/lib/api/dashboard";
import { useQuery } from "@tanstack/react-query";

export function TabAgentInvocations({ runId, agentPath }: { runId: string; agentPath: string }) {
  const query = useQuery({
    queryKey: ["agent-invocations", runId, agentPath] as const,
    queryFn: () => dashboardApi.agentInvocations(runId, agentPath),
    staleTime: 30_000,
  });

  if (query.isLoading) {
    return <div className="p-5 text-[12px] text-muted-2">loading invocations…</div>;
  }
  const rows = query.data?.invocations ?? [];
  if (rows.length === 0) {
    return <div className="p-5 text-[12px] text-muted-2">no invocations recorded yet</div>;
  }

  return (
    <div className="p-5">
      <InvocationsList
        invocations={rows}
        agentPath={agentPath}
        density="full"
        initiallyExpandedId={rows[rows.length - 1]?.id ?? null}
      />
    </div>
  );
}
