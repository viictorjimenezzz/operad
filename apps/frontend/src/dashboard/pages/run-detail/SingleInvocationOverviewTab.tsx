import { DefinitionPanel } from "@/components/agent-view/overview/definition-section";
import { IOHero } from "@/components/agent-view/overview/io-hero";
import { ActivityStrip } from "@/components/agent-view/overview/run-status-strip";
import { StructureOverview } from "@/components/agent-view/overview/structure-overview";
import { EmptyState, Eyebrow } from "@/components/ui";
import { HashRow, type HashKey } from "@/components/ui/hash-row";
import { useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { RunInvocationsResponse } from "@/lib/types";
import { useParams } from "react-router-dom";

export function SingleInvocationOverviewTab() {
  const { runId } = useParams<{ runId: string }>();
  const summary = useRunSummary(runId);
  const invocations = useRunInvocations(runId);

  if (!runId) return null;
  if (summary.isLoading || invocations.isLoading) {
    return (
      <div className="h-full overflow-auto p-4">
        <div className="h-9 animate-pulse rounded bg-bg-2" />
      </div>
    );
  }
  if (!summary.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState title="run not found" description="the invocation summary is unavailable" />
      </div>
    );
  }

  const parsed = RunInvocationsResponse.safeParse(invocations.data);
  const rows = parsed.success ? parsed.data.invocations : [];
  const latest = rows[rows.length - 1] ?? null;
  const previous = rows.length >= 2 ? rows[rows.length - 2] : null;

  const hashKeys: HashKey[] = [
    "hash_content",
    "hash_model",
    "hash_prompt",
    "hash_input",
    "hash_output_schema",
    "hash_graph",
    "hash_config",
  ];

  const hashCurrent: Partial<Record<HashKey, string | null>> = Object.fromEntries(
    hashKeys.map((k) => [k, (latest as Record<string, unknown> | null)?.[k] as string | null ?? null]),
  );
  const hashPrevious: Partial<Record<HashKey, string | null>> | undefined = previous
    ? Object.fromEntries(
        hashKeys.map((k) => [k, (previous as Record<string, unknown>)[k] as string | null ?? null]),
      )
    : undefined;

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-4 p-4">
        <ActivityStrip
          dataSummary={summary.data}
          dataInvocations={invocations.data}
          runId={runId}
        />
        <IOHero dataInvocations={invocations.data} runId={runId} />
        <DefinitionPanel
          dataSummary={summary.data}
          dataInvocations={invocations.data}
          runId={runId}
        />
        <section className="space-y-2 border-t border-border pt-4">
          <Eyebrow>reproducibility</Eyebrow>
          <HashRow current={hashCurrent} previous={hashPrevious} />
        </section>
        <StructureOverview runId={runId} hashContent={summary.data.hash_content ?? null} />
      </div>
    </div>
  );
}
