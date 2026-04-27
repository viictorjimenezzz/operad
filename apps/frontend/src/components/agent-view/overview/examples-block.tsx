import { FieldTree, Section } from "@/components/ui";
import { useAgentMeta } from "@/hooks/use-runs";
import { RunSummary } from "@/lib/types";

export interface ExamplesBlockProps {
  dataSummary?: unknown;
  summary?: unknown;
  runId?: string;
}

export function ExamplesBlock(props: ExamplesBlockProps) {
  const summaryParsed = RunSummary.safeParse(props.dataSummary ?? props.summary);
  if (!summaryParsed.success || !props.runId || !summaryParsed.data.root_agent_path) {
    return (
      <Section title="Examples" summary="not available" disabled>
        <span />
      </Section>
    );
  }
  const meta = useAgentMeta(props.runId, summaryParsed.data.root_agent_path);
  const examples = meta.data?.examples ?? [];
  const summary =
    examples.length === 0
      ? "no canonical examples shipped"
      : `${examples.length} canonical example${examples.length === 1 ? "" : "s"}`;

  const first = examples[0] ?? null;

  const succinct =
    first !== null ? (
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2">
            in
          </div>
          <div className="rounded-md bg-bg-inset px-2 py-1.5">
            <FieldTree data={first.input} preview />
          </div>
        </div>
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2">
            out
          </div>
          <div className="rounded-md bg-bg-inset px-2 py-1.5">
            <FieldTree data={first.output} preview />
          </div>
        </div>
      </div>
    ) : null;

  return (
    <Section
      title="Examples"
      summary={summary}
      {...(succinct ? { succinct } : {})}
      disabled={examples.length === 0}
    >
      <div className="space-y-3">
        {examples.map((ex, i) => (
          <div key={i} className="rounded-md border border-border bg-bg-inset p-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-2">
              example {i + 1}
            </div>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div>
                <div className="mb-1 text-[11px] text-muted">in</div>
                <FieldTree data={ex.input} defaultDepth={2} hideCopy />
              </div>
              <div>
                <div className="mb-1 text-[11px] text-muted">out</div>
                <FieldTree data={ex.output} defaultDepth={2} hideCopy />
              </div>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
