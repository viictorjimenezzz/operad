import { Button, Eyebrow, FieldTree } from "@/components/ui";
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
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <InvocationValuePanel label="Input" data={input} />
        <InvocationValuePanel label="Output" data={output} />
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

function InvocationValuePanel({ label, data }: { label: string; data: unknown }) {
  const empty = data === null || data === undefined;

  return (
    <div className="flex h-[360px] flex-col rounded-md border border-border bg-bg-2">
      <div className="border-b border-border/60 px-3 py-2">
        <Eyebrow>{label}</Eyebrow>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-3 py-2">
        {empty ? (
          <div className="text-[12px] text-muted-2">no payload captured</div>
        ) : (
          <FieldTree
            data={data}
            defaultDepth={4}
            hideCopy
            truncateStrings={false}
            layout="stacked"
          />
        )}
      </div>
    </div>
  );
}
