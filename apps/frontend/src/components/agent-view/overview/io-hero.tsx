import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { Button } from "@/components/ui";
import { useManifest } from "@/hooks/use-runs";
import { dashboardApi } from "@/lib/api/dashboard";
import { RunInvocationsResponse, RunSummary } from "@/lib/types";
import { Copy, Play, RotateCcw } from "lucide-react";
import { useState } from "react";

export interface IOHeroProps {
  dataInvocations?: unknown;
  dataSummary?: unknown;
  sourceInvocations?: unknown;
  sourceSummary?: unknown;
  runId?: string;
}

export function IOHero(props: IOHeroProps) {
  const parsed = RunInvocationsResponse.safeParse(props.dataInvocations ?? props.sourceInvocations);
  const summary = RunSummary.safeParse(props.dataSummary ?? props.sourceSummary);
  const manifest = useManifest();
  const rows = parsed.success ? parsed.data.invocations : [];
  const latest = rows[rows.length - 1] ?? null;
  const input = latest?.input ?? null;
  const output = latest?.output ?? null;
  const runId = props.runId ?? (summary.success ? summary.data.run_id : null);
  const agentPath =
    parsed.success && parsed.data.agent_path
      ? parsed.data.agent_path
      : summary.success
        ? summary.data.root_agent_path
        : null;
  const canReplay = Boolean(
    manifest.data?.allowExperiment && runId && agentPath && isRecord(input),
  );
  const cassetteActive = Boolean(manifest.data?.cassetteMode);
  const [replayResult, setReplayResult] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  const copyJson = () => {
    navigator.clipboard.writeText(JSON.stringify({ input, output }, null, 2));
  };

  const replay = async () => {
    if (!canReplay || !runId || !agentPath || !isRecord(input)) return;
    setPending(true);
    try {
      const result = await dashboardApi.agentInvoke(runId, agentPath, { input });
      setReplayResult(result.response);
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="space-y-2">
      <div className="grid min-h-[260px] grid-cols-1 gap-3 xl:grid-cols-2">
        <IOFieldPreview label="Input" data={input} defaultExpanded className="min-h-[260px]" />
        <IOFieldPreview label="Output" data={output} defaultExpanded className="min-h-[260px]" />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="ghost" onClick={copyJson}>
          <Copy size={13} />
          Copy as JSON
        </Button>
        <Button size="sm" variant="default" onClick={replay} disabled={!canReplay || pending}>
          <Play size={13} />
          {pending ? "Replaying..." : "Replay"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={!cassetteActive}
          title={cassetteActive ? undefined : "Cassette mode is not active"}
        >
          <RotateCcw size={13} />
          Cassette replay
        </Button>
      </div>
      {replayResult !== null ? (
        <details className="rounded-lg border border-border bg-bg-1 p-3 text-[12px] text-text">
          <summary className="cursor-pointer text-muted">replay result</summary>
          <pre className="mt-2 max-h-72 overflow-auto rounded bg-bg-inset p-2 font-mono text-[11px]">
            {JSON.stringify(replayResult, null, 2)}
          </pre>
        </details>
      ) : null}
    </section>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
