import { InvocationValueBlock } from "@/components/agent-view/overview/invocation-detail-blocks";
import { RunInvocationsResponse } from "@/lib/types";

export interface IOHeroProps {
  dataInvocations?: unknown;
  sourceInvocations?: unknown;
  runId?: string;
}

export function IOHero(props: IOHeroProps) {
  const parsed = RunInvocationsResponse.safeParse(props.dataInvocations ?? props.sourceInvocations);
  const rows = parsed.success ? parsed.data.invocations : [];
  const latest = rows[rows.length - 1] ?? null;
  const input = latest?.input ?? null;
  const output = latest?.output ?? null;

  return (
    <section className="space-y-2">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <InvocationValueBlock label="Input" data={input} />
        <InvocationValueBlock label="Output" data={output} />
      </div>
    </section>
  );
}
