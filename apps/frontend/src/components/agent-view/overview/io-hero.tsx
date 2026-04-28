import { IOFieldPreview } from "@/components/agent-view/overview/io-field-preview";
import { Button } from "@/components/ui";
import { RunInvocationsResponse } from "@/lib/types";
import { Copy } from "lucide-react";

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

  const copyJson = () => {
    navigator.clipboard.writeText(JSON.stringify({ input, output }, null, 2));
  };

  return (
    <section className="space-y-2">
      <div className="grid min-h-[260px] grid-cols-1 gap-3 xl:grid-cols-2">
        <IOFieldPreview label="Input" data={input} defaultExpanded className="min-h-[260px]" />
        <IOFieldPreview label="Output" data={output} defaultExpanded className="min-h-[260px]" />
      </div>
      <div className="flex items-center">
        <Button size="sm" variant="ghost" onClick={copyJson}>
          <Copy size={13} />
          Copy as JSON
        </Button>
      </div>
    </section>
  );
}
