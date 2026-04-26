import { HashChip } from "@/components/agent-view/metadata/hash-chip";
import { InvocationsTable } from "@/components/agent-view/metadata/invocations-table";
import { ScriptOriginChip } from "@/components/agent-view/metadata/script-origin-chip";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AgentInvocationsResponse, RunSummary } from "@/lib/types";
import { formatDurationMs, truncateMiddle } from "@/lib/utils";

interface AgentMetadataPanelProps {
  summary: RunSummary | null | undefined;
  invocations: AgentInvocationsResponse | null | undefined;
  runId: string | undefined;
}

export function AgentMetadataPanel({ summary, invocations, runId }: AgentMetadataPanelProps) {
  const state = summary?.state ?? "running";
  const live = state === "running";
  const latest = invocations?.invocations.at(-1);

  return (
    <Card>
      <CardHeader>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <CardTitle className="text-text">agent metadata</CardTitle>
          <Badge variant={state === "running" ? "live" : state === "error" ? "error" : "ended"}>
            {state}
          </Badge>
          <span className="truncate font-mono text-xs text-text" title={invocations?.agent_path}>
            {invocations?.agent_path ?? summary?.root_agent_path ?? "agent"}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted">run</span>
          <code className="font-mono text-text">
            {truncateMiddle(runId ?? summary?.run_id ?? "", 24)}
          </code>
          <span className="text-muted">hash content</span>
          <HashChip value={latest?.hash_content} />
          <span className="text-muted">script</span>
          <ScriptOriginChip script={latest?.script} />
          <span className="text-muted">duration</span>
          <span className="font-mono text-text">{formatDurationMs(summary?.duration_ms)}</span>
        </div>
        <InvocationsTable data={invocations} live={live} />
      </CardContent>
    </Card>
  );
}
