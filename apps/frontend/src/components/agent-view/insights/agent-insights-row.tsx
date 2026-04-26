import { BackendBadges } from "@/components/agent-view/insights/backend-badges";
import { CostLatencySparklines } from "@/components/agent-view/insights/cost-latency-sparklines";
import { DriftStrip } from "@/components/agent-view/insights/drift-strip";
import { FingerprintCard } from "@/components/agent-view/insights/fingerprint-card";
import { ChunkReplay } from "@/components/agent-view/insights/chunk-replay";
import { ValueDistribution } from "@/components/agent-view/insights/value-distribution";
import { Card, CardContent } from "@/components/ui/card";
import { dashboardApi } from "@/lib/api/dashboard";
import {
  AgentMetaResponse,
  type RunInvocation,
  RunInvocationsResponse,
  RunSummary,
} from "@/lib/types";
import { useQuery } from "@tanstack/react-query";

export interface AgentInsightsRowProps {
  summary?: unknown;
  invocations?: unknown;
  runId?: string | null;
  dataSummary?: unknown;
  dataInvocations?: unknown;
}

export function AgentInsightsRow(props: AgentInsightsRowProps) {
  const rawSummary = props.dataSummary ?? props.summary;
  const rawInvocations = props.dataInvocations ?? props.invocations;
  const summaryParsed = RunSummary.safeParse(rawSummary);
  if (!summaryParsed.success) {
    return (
      <ContractError
        title="invalid summary contract"
        issues={summaryParsed.error.issues.map((i) => i.path.join("."))}
      />
    );
  }
  const invocationsParsed = RunInvocationsResponse.safeParse(rawInvocations);
  if (!invocationsParsed.success) {
    return (
      <ContractError
        title="invalid invocations contract"
        issues={invocationsParsed.error.issues.map((issue) => issue.path.join("."))}
      />
    );
  }

  const summary = summaryParsed.data;
  const invocations = invocationsParsed.data.invocations;
  const rootPath = summary.root_agent_path ?? invocationsParsed.data.agent_path ?? null;
  const runId = props.runId ?? summary.run_id;

  const metaQuery = useQuery({
    queryKey: ["run", "agent-meta", runId, rootPath] as const,
    queryFn: () => {
      if (!runId || !rootPath) throw new Error("runId and rootPath are required");
      return dashboardApi.agentMeta(runId, rootPath);
    },
    enabled: !!runId && !!rootPath,
    retry: false,
  });
  const meta = parseMeta(metaQuery.data);

  const first = invocations[0] ?? null;
  const last = invocations[invocations.length - 1] ?? null;
  const hashes: Record<string, string | null> = {
    hash_model: last?.hash_model ?? first?.hash_model ?? null,
    hash_prompt: last?.hash_prompt ?? first?.hash_prompt ?? null,
    hash_graph: last?.hash_graph ?? first?.hash_graph ?? null,
    hash_input: last?.hash_input ?? first?.hash_input ?? null,
    hash_output_schema: last?.hash_output_schema ?? first?.hash_output_schema ?? null,
    hash_config: last?.hash_config ?? first?.hash_config ?? null,
    hash_content: last?.hash_content ?? first?.hash_content ?? null,
  };

  const allDistributions = toInputDistributions(invocations);
  const distributions = allDistributions.slice(0, 4);
  const hiddenCount = Math.max(0, allDistributions.length - distributions.length);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 xl:grid-cols-2">
        <FingerprintCard hashes={hashes} />
        <DriftStrip invocations={invocations} rootPath={rootPath} summary={summary} />
        <BackendBadges invocations={invocations} summaryRaw={rawSummary} meta={meta} />
        <CostLatencySparklines invocations={invocations} />
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {distributions.length === 0 ? (
          <Card className="md:col-span-2 xl:col-span-4">
            <CardContent className="text-[0.72rem] text-muted">
              no input-shape data available from invocations
            </CardContent>
          </Card>
        ) : (
          distributions.map((entry) => (
            <ValueDistribution
              key={entry.label}
              label={entry.label}
              values={entry.values}
              agentPath={rootPath}
              side="in"
            />
          ))
        )}
      </div>
      {hiddenCount > 0 ? (
        <p className="m-0 text-[0.68rem] text-muted">+{hiddenCount} more fields</p>
      ) : null}
      {runId && rootPath ? (
        <ChunkReplay runId={runId} agentPath={rootPath} invocations={invocations} />
      ) : null}
      {metaQuery.error ? (
        <p className="m-0 text-[0.68rem] text-warn">
          agent meta unavailable; showing invocation-derived badges
        </p>
      ) : null}
    </div>
  );
}

function parseMeta(value: unknown): AgentMetaResponse | null {
  if (!value) return null;
  const parsed = AgentMetaResponse.safeParse(value);
  return parsed.success ? parsed.data : null;
}

function toInputDistributions(
  invocations: RunInvocation[],
): Array<{ label: string; values: unknown[] }> {
  const map = new Map<string, unknown[]>();
  for (const invocation of invocations) {
    if (
      !invocation.input ||
      typeof invocation.input !== "object" ||
      Array.isArray(invocation.input)
    )
      continue;
    for (const [key, value] of Object.entries(invocation.input as Record<string, unknown>)) {
      const list = map.get(key) ?? [];
      list.push(value);
      map.set(key, list);
    }
  }
  return [...map.entries()].map(([label, values]) => ({ label, values }));
}

function ContractError({ title, issues }: { title: string; issues: string[] }) {
  return (
    <Card>
      <CardContent className="space-y-1 p-3">
        <p className="m-0 text-[0.75rem] font-semibold text-err">{title}</p>
        {issues.slice(0, 5).map((issue) => (
          <p key={issue} className="m-0 font-mono text-[0.68rem] text-muted">
            {issue || "(root)"}
          </p>
        ))}
      </CardContent>
    </Card>
  );
}
