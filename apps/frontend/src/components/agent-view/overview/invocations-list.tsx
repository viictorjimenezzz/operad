import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { Eyebrow, HashTag, IconButton, Pill, Sparkline } from "@/components/ui";
import { type RunInvocation, RunInvocationsResponse, RunSummary } from "@/lib/types";
import { cn, formatCost, formatDurationMs, formatRelativeTime, formatTokens } from "@/lib/utils";
import { useUIStore } from "@/stores";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ExternalLink, GitCompare } from "lucide-react";
import { useMemo, useState } from "react";

export interface InvocationsListProps {
  /** When true, exclude the most recent invocation (the LatestInvocationCard renders it). */
  skipLatest?: boolean;
  /** When true and the list ends up empty, render nothing. */
  hideIfEmpty?: boolean;
  density?: "compact" | "full";
  invocations?: unknown;
  dataSummary?: unknown;
  dataInvocations?: unknown;
  summary?: unknown;
  runId?: string | undefined;
  /** Direct rows path (used by the Invocations tab). */
  agentPath?: string;
  initiallyExpandedId?: string | null;
}

interface InternalProps {
  rows: RunInvocation[];
  agentPath: string;
  density: "compact" | "full";
  initiallyExpandedId: string | null;
}

function parsePayload(props: InvocationsListProps): InternalProps | null {
  // Path 1: invocation array provided directly via Phase 2 InvocationsTab.
  if (Array.isArray(props.invocations)) {
    return {
      rows: props.invocations as RunInvocation[],
      agentPath: props.agentPath ?? "",
      density: props.density ?? "compact",
      initiallyExpandedId: props.initiallyExpandedId ?? null,
    };
  }
  // Path 2: json-render with dataSummary/dataInvocations.
  const rawInvocations = props.dataInvocations ?? props.invocations;
  const parsed = RunInvocationsResponse.safeParse(rawInvocations);
  if (!parsed.success) return null;
  const rawSummary = props.dataSummary ?? props.summary;
  const summary = RunSummary.safeParse(rawSummary);
  return {
    rows: parsed.data.invocations,
    agentPath:
      parsed.data.agent_path ?? (summary.success ? (summary.data.root_agent_path ?? "") : ""),
    density: props.density ?? "compact",
    initiallyExpandedId: props.initiallyExpandedId ?? null,
  };
}

export function InvocationsList(props: InvocationsListProps) {
  const internal = parsePayload(props);
  if (!internal) return null;
  const all = internal.rows;
  const slice = props.skipLatest ? all.slice(0, all.length - 1) : all;
  if (slice.length === 0 && (props.hideIfEmpty ?? true)) return null;

  return (
    <Body
      rows={slice}
      agentPath={internal.agentPath}
      density={internal.density}
      initiallyExpandedId={internal.initiallyExpandedId}
    />
  );
}

function Body({ rows, agentPath, density, initiallyExpandedId }: InternalProps) {
  const [expandedId, setExpandedId] = useState<string | null>(initiallyExpandedId);
  const setComparison = useUIStore((s) => s.setComparisonInvocation);
  const comparisonInvocationId = useUIStore((s) => s.comparisonInvocationId);
  const clearComparison = useUIStore((s) => s.clearComparisonInvocation);

  const latencyValues = useMemo(() => rows.map((r) => r.latency_ms ?? null), [rows]);

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => b.started_at - a.started_at);
  }, [rows]);

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-bg-1">
      <header className="flex items-center justify-between gap-2 border-b border-border bg-bg-2/40 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Eyebrow>
            {rows.length === 1 ? "1 previous invocation" : `${rows.length} previous invocations`}
          </Eyebrow>
        </div>
        <Sparkline values={latencyValues} width={120} height={20} className="text-accent" />
      </header>
      <ol>
        {sorted.map((row, i) => (
          <InvocationRow
            key={row.id}
            row={row}
            index={rows.length - i}
            agentPath={agentPath}
            density={density}
            expanded={expandedId === row.id}
            onToggle={() => setExpandedId((curr) => (curr === row.id ? null : row.id))}
            isComparisonAnchor={comparisonInvocationId === row.id}
            onCompare={() => {
              if (comparisonInvocationId === row.id) clearComparison();
              else setComparison(row.id, agentPath);
            }}
          />
        ))}
      </ol>
    </section>
  );
}

function InvocationRow({
  row,
  index,
  agentPath,
  density,
  expanded,
  onToggle,
  isComparisonAnchor,
  onCompare,
}: {
  row: RunInvocation;
  index: number;
  agentPath: string;
  density: "compact" | "full";
  expanded: boolean;
  onToggle: () => void;
  isComparisonAnchor: boolean;
  onCompare: () => void;
}) {
  void agentPath;

  return (
    <li className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "grid w-full cursor-pointer grid-cols-[40px_120px_90px_120px_90px_1fr_auto] items-center gap-3 px-4 py-2.5 text-left text-[12px] transition-colors",
          "hover:bg-bg-2",
          expanded && "bg-bg-2",
        )}
      >
        <span className="font-mono text-[11px] text-muted-2 tabular-nums">#{index}</span>
        <span className="truncate text-muted">{formatRelativeTime(row.started_at)}</span>
        <span className={cn("font-mono tabular-nums", latencyClass(row.latency_ms))}>
          {formatDurationMs(row.latency_ms)}
        </span>
        <span className="font-mono tabular-nums text-muted">
          {formatTokens(row.prompt_tokens)} / {formatTokens(row.completion_tokens)}
        </span>
        <span className="font-mono tabular-nums text-muted">{formatCost(row.cost_usd)}</span>
        <span className="flex items-center gap-2">
          {row.status === "error" ? (
            <Pill tone="error" size="sm">
              error
            </Pill>
          ) : (
            <Pill tone="ok" size="sm">
              ok
            </Pill>
          )}
          {row.hash_prompt ? <HashTag hash={row.hash_prompt} size="sm" /> : null}
        </span>
        <span className="flex items-center gap-1.5">
          <IconButton
            size="sm"
            aria-label={isComparisonAnchor ? "clear comparison anchor" : "set as comparison anchor"}
            active={isComparisonAnchor}
            onClick={(e) => {
              e.stopPropagation();
              onCompare();
            }}
            title={
              isComparisonAnchor
                ? "comparison anchor — click again to clear"
                : "diff against this invocation"
            }
          >
            <GitCompare size={12} />
          </IconButton>
          {row.langfuse_url ? (
            <a
              href={row.langfuse_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded p-1 text-muted-2 hover:text-text"
              aria-label="Open invocation in Langfuse"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink size={12} />
            </a>
          ) : null}
          <ChevronDown
            size={13}
            className={cn(
              "flex-shrink-0 text-muted-2 transition-transform duration-150",
              expanded && "rotate-180",
            )}
          />
        </span>
      </button>
      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-1 gap-3 border-t border-border bg-bg-1 px-4 py-3 lg:grid-cols-2">
              <IOFieldPreview label="Input" data={row.input} defaultExpanded={density === "full"} />
              <IOFieldPreview
                label="Output"
                data={row.output}
                defaultExpanded={density === "full"}
              />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </li>
  );
}

function latencyClass(latencyMs: number | null | undefined): string {
  if (latencyMs == null || !Number.isFinite(latencyMs)) return "text-muted-2";
  if (latencyMs < 1_000) return "text-[--color-ok]";
  if (latencyMs < 5_000) return "text-[--color-warn]";
  return "text-[--color-err]";
}
