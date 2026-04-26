import { BackendBadges } from "@/components/agent-view/insights/backend-badges";
import { CostLatencySparklines } from "@/components/agent-view/insights/cost-latency-sparklines";
import { DriftStrip } from "@/components/agent-view/insights/drift-strip";
import { FingerprintCard } from "@/components/agent-view/insights/fingerprint-card";
import { ValueDistribution } from "@/components/agent-view/insights/value-distribution";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { dashboardApi } from "@/lib/api/dashboard";
import type { AgentInvocationsResponse, AgentMetaResponse, RunSummary } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

interface AgentInsightsRowProps {
  summary: RunSummary | null | undefined;
  invocations: AgentInvocationsResponse | null | undefined;
}

function inferInputValues(
  invocations: AgentInvocationsResponse | null | undefined,
): Record<string, unknown[]> {
  // Backend root invocations endpoint does not include input payloads; keep placeholder buckets for now.
  const fields: Record<string, unknown[]> = {};
  for (const row of invocations?.invocations ?? []) {
    const key = row.status;
    const list = fields[key] ?? [];
    list.push(row.latency_ms ?? 0);
    fields[key] = list;
  }
  return fields;
}

export function AgentInsightsRow({ summary, invocations }: AgentInsightsRowProps) {
  const agentPath = invocations?.agent_path ?? summary?.root_agent_path ?? "";

  const metaQuery = useQuery<AgentMetaResponse>({
    queryKey: ["agent-meta", summary?.run_id, agentPath],
    queryFn: async () => {
      if (!summary?.run_id || !agentPath) throw new Error("missing run or path");
      return dashboardApi.agentMeta(summary.run_id, agentPath);
    },
    enabled: Boolean(summary?.run_id && agentPath),
    staleTime: 30_000,
  });

  const latest = invocations?.invocations.at(-1) ?? null;
  const valueMap = inferInputValues(invocations);

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
        <FingerprintCard summary={summary} latest={latest} />
        <Card>
          <CardHeader>
            <CardTitle>prompt drift</CardTitle>
          </CardHeader>
          <CardContent>
            <DriftStrip agentPath={agentPath} invocations={invocations?.invocations ?? []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>backend + config</CardTitle>
          </CardHeader>
          <CardContent>
            <BackendBadges meta={metaQuery.data} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>cost + latency</CardTitle>
          </CardHeader>
          <CardContent>
            <CostLatencySparklines invocations={invocations?.invocations ?? []} />
          </CardContent>
        </Card>
      </div>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
        {Object.entries(valueMap)
          .slice(0, 4)
          .map(([name, values]) => (
            <ValueDistribution key={name} name={name} values={values} />
          ))}
      </div>
    </div>
  );
}
