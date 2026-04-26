import { Button } from "@/components/ui/button";
import { useManifest } from "@/hooks/use-runs";
import { langfuseUrlFor } from "@/lib/langfuse";
import { RunSummary } from "@/lib/types";
import { formatCost, formatTokens } from "@/lib/utils";
import { ExternalLink } from "lucide-react";

interface LangfuseSummaryCardProps {
  runId: string | null;
  data: unknown;
}

export function LangfuseSummaryCard({ runId, data }: LangfuseSummaryCardProps) {
  const manifest = useManifest();
  const langfuseUrl = manifest.data?.langfuseUrl ?? null;

  const parsed = RunSummary.safeParse(data);
  const summary = parsed.success ? parsed.data : null;

  const errorCount = summary
    ? Object.entries(summary.event_counts)
        .filter(([k]) => k.includes("error"))
        .reduce((acc, [, v]) => acc + v, 0)
    : 0;

  const totalTokens = summary
    ? (summary.prompt_tokens ?? 0) + (summary.completion_tokens ?? 0)
    : null;

  const traceHref = langfuseUrl && runId ? langfuseUrlFor(langfuseUrl, runId) : null;

  return (
    <div className="rounded-md border border-border bg-bg-1 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium uppercase tracking-wide text-muted-foreground text-xs">
          Langfuse
        </span>
        {traceHref && (
          <a
            href={traceHref}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open trace in Langfuse"
          >
            <ExternalLink className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
          </a>
        )}
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5">
        <dt className="text-muted-foreground">spans</dt>
        <dd>{summary ? summary.event_total : "—"}</dd>
        <dt className="text-muted-foreground">tokens</dt>
        <dd>{totalTokens != null ? formatTokens(totalTokens) : "—"}</dd>
        <dt className="text-muted-foreground">cost</dt>
        <dd>{summary?.cost?.cost_usd != null ? formatCost(summary.cost.cost_usd) : "—"}</dd>
        <dt className="text-muted-foreground">errors</dt>
        <dd>{summary ? errorCount : "—"}</dd>
      </dl>
      {traceHref && (
        <Button
          variant="ghost"
          size="sm"
          className="mt-2 self-start"
          onClick={() => window.open(traceHref, "_blank", "noopener")}
        >
          view in Langfuse →
        </Button>
      )}
      {/* TODO: per-event ↗ links require spanId in event metadata; not yet populated by OtelObserver */}
    </div>
  );
}
