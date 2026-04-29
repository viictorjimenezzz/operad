import { InvocationPromptBlock } from "@/components/agent-view/overview/invocation-detail-blocks";
import { IOHero } from "@/components/agent-view/overview/io-hero";
import { ActivityStrip } from "@/components/agent-view/overview/run-status-strip";
import { EmptyState, Eyebrow, FieldTree } from "@/components/ui";
import { type HashKey, HashRow } from "@/components/ui/hash-row";
import { useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { type RunInvocation, RunInvocationsResponse } from "@/lib/types";
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
    hashKeys.map((k) => [
      k,
      ((latest as Record<string, unknown> | null)?.[k] as string | null) ?? null,
    ]),
  );
  const hashPrevious: Partial<Record<HashKey, string | null>> | undefined = previous
    ? Object.fromEntries(
        hashKeys.map((k) => [
          k,
          ((previous as Record<string, unknown>)[k] as string | null) ?? null,
        ]),
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
        <PromptPanel invocation={latest} />
        <RuntimeConfigPanel invocation={latest} />
        <section className="space-y-2 border-t border-border pt-4">
          <Eyebrow>reproducibility</Eyebrow>
          <HashRow
            current={hashCurrent}
            {...(hashPrevious !== undefined ? { previous: hashPrevious } : {})}
          />
        </section>
      </div>
    </div>
  );
}

function PromptPanel({ invocation }: { invocation: RunInvocation | null }) {
  const system = invocation?.prompt_system?.trim() || null;
  const user = invocation?.prompt_user?.trim() || null;
  const renderer = invocation?.renderer ?? null;

  return (
    <section className="space-y-3 border-t border-border pt-4">
      <div className="flex items-center gap-2">
        <Eyebrow>prompt</Eyebrow>
        {renderer ? (
          <span className="rounded border border-border bg-bg-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">
            {renderer}
          </span>
        ) : null}
      </div>
      {system || user ? (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <InvocationPromptBlock label="system" value={system} />
          <InvocationPromptBlock label="user" value={user} />
        </div>
      ) : (
        <div className="rounded-md border border-border bg-bg-2 px-3 py-2 text-[12px] text-muted-2">
          no prompt captured
        </div>
      )}
    </section>
  );
}

function RuntimeConfigPanel({ invocation }: { invocation: RunInvocation | null }) {
  const config = invocation?.config ?? null;
  const hasConfig = config !== null && Object.keys(config).length > 0;

  return (
    <section className="space-y-2 border-t border-border pt-4">
      <Eyebrow>runtime config</Eyebrow>
      <div className="max-h-[360px] overflow-auto rounded-md border border-border bg-bg-2 px-3 py-2">
        {hasConfig ? (
          <FieldTree
            data={config}
            defaultDepth={3}
            hideCopy
            truncateStrings={false}
            layout="stacked"
          />
        ) : (
          <span className="text-[12px] text-muted-2">no runtime configuration captured</span>
        )}
      </div>
    </section>
  );
}
