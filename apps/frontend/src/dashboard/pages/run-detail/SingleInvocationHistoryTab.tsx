import {
  InvocationPromptBlock,
  InvocationValueBlock,
} from "@/components/agent-view/overview/invocation-detail-blocks";
import { EmptyState, Eyebrow, FieldTree, Metric, Pill } from "@/components/ui";
import { useRunInvocations } from "@/hooks/use-runs";
import { useUrlState } from "@/hooks/use-url-state";
import { type RunInvocation, RunInvocationsResponse } from "@/lib/types";
import { cn, formatCost, formatDurationMs, formatRelativeTime, formatTokens } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import { useParams } from "react-router-dom";

export function SingleInvocationHistoryTab() {
  const { runId } = useParams<{ runId: string }>();
  const invocations = useRunInvocations(runId);
  const [selectedId, setSelectedId] = useUrlState("invocation");

  if (!runId) return null;
  if (invocations.isLoading) {
    return <div className="p-4 text-xs text-muted">loading history...</div>;
  }

  const parsed = RunInvocationsResponse.safeParse(invocations.data);
  const rows = parsed.success
    ? [...parsed.data.invocations].sort((a, b) => a.started_at - b.started_at)
    : [];

  if (rows.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState
          title="no invocation history"
          description="this run has not recorded agent invocations yet"
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4">
      <div className="mx-auto max-w-[1180px]">
        <ol className="relative flex flex-col gap-4 border-l border-border pl-5">
          {rows.map((row, index) => (
            <li key={row.id}>
              <HistoryRow
                row={row}
                index={index}
                expanded={selectedId === row.id}
                onToggle={() => setSelectedId(selectedId === row.id ? null : row.id)}
              />
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function HistoryRow({
  row,
  index,
  expanded,
  onToggle,
}: {
  row: RunInvocation;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const promptTokens = row.prompt_tokens ?? null;
  const completionTokens = row.completion_tokens ?? null;
  const hasTokens = promptTokens != null || completionTokens != null;
  const totalTokens = (promptTokens ?? 0) + (completionTokens ?? 0);
  const hasCost = typeof row.cost_usd === "number" && Number.isFinite(row.cost_usd);

  return (
    <section
      className={cn(
        "relative rounded-lg border bg-bg-1",
        expanded ? "border-accent ring-1 ring-[--color-accent-dim]" : "border-border",
      )}
    >
      <span className="absolute -left-[27px] top-3 h-3 w-3 rounded-full border border-border bg-bg-1" />
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 px-3 py-3 text-left transition-colors hover:bg-bg-2"
      >
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
            <div className="text-[12px] font-medium text-text">invocation {index + 1}</div>
            <span className="font-mono text-[11px] text-muted">{row.id}</span>
            <Pill tone={row.status === "error" ? "error" : "ok"} size="sm">
              {row.status === "error" ? "error" : "ok"}
            </Pill>
            <span className="text-[12px] text-muted">{formatRelativeTime(row.started_at)}</span>
            <Metric label="duration" value={formatDurationMs(row.latency_ms)} />
            {hasTokens ? <Metric label="tokens" value={formatTokens(totalTokens)} /> : null}
            {hasCost ? <Metric label="cost" value={formatCost(row.cost_usd)} /> : null}
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <CompactValuePreview label="input" data={row.input} />
            <CompactValuePreview label="output" data={row.output} />
          </div>
        </div>
        <ChevronDown
          aria-hidden
          size={15}
          className={cn(
            "mt-0.5 flex-shrink-0 text-muted-2 transition-transform duration-150",
            expanded && "rotate-180",
          )}
        />
      </button>
      {expanded ? (
        <div className="space-y-4 border-t border-border px-3 py-3">
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <InvocationValueBlock
              label="Input"
              data={row.input}
              bodyClassName="h-[260px]"
              defaultDepth={4}
            />
            <InvocationValueBlock
              label="Output"
              data={row.output}
              bodyClassName="h-[260px]"
              defaultDepth={4}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <InvocationPromptBlock
              label="System Prompt"
              value={row.prompt_system}
              bodyClassName="max-h-[320px]"
            />
            <InvocationPromptBlock
              label="User Prompt"
              value={row.prompt_user}
              bodyClassName="max-h-[320px]"
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function CompactValuePreview({ label, data }: { label: string; data: unknown }) {
  const empty = data === null || data === undefined;
  return (
    <div className="min-w-0">
      <Eyebrow>{label}</Eyebrow>
      <div className="mt-1.5 min-h-[76px] overflow-hidden rounded-md border border-border bg-bg-inset px-2 py-1.5">
        {empty ? (
          <span className="text-[12px] text-muted-2">no payload captured</span>
        ) : (
          <FieldTree data={data} preview hideCopy />
        )}
      </div>
    </div>
  );
}
