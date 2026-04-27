import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { ExternalLink } from "lucide-react";

export interface SynthesisCardProps {
  answer: string | null;
  childHref: string | null;
  loading?: boolean;
}

export function SynthesisCard({ answer, childHref, loading = false }: SynthesisCardProps) {
  return (
    <section className="rounded-lg border border-border bg-bg-1 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="m-0 text-[15px] font-semibold text-text">Synthesized answer</h2>
          <p className="m-0 mt-1 text-[11px] text-muted">Final artifact from the synthesizer</p>
        </div>
        {childHref ? (
          <a
            className="inline-flex items-center gap-1.5 rounded border border-border px-2 py-1 text-[11px] text-text transition-colors hover:border-border-strong hover:bg-bg-2"
            href={childHref}
          >
            <ExternalLink size={12} />
            Open synthesizer run
          </a>
        ) : null}
      </div>
      {loading ? (
        <div className="h-24 animate-pulse rounded bg-bg-2" />
      ) : answer ? (
        <MarkdownView value={answer} />
      ) : (
        <EmptyState
          title="synthesis not available"
          description="the synthesizer child run has not emitted a final answer yet"
          className="min-h-32"
        />
      )}
    </section>
  );
}
