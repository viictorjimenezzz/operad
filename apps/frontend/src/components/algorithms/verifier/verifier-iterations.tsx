import { EmptyState } from "@/components/ui/empty-state";
import { MarkdownView } from "@/components/ui/markdown";
import { useUrlState } from "@/hooks/use-url-state";
import { IterationsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface VerifierIterationsProps {
  data: unknown;
}

export function VerifierIterations({ data }: VerifierIterationsProps) {
  const parsed = IterationsResponse.safeParse(data);
  const [iterParam, setIterParam] = useUrlState("iter");

  if (!parsed.success || parsed.data.iterations.length === 0) {
    return <EmptyState title="no verifier iterations" description="waiting for verify events" />;
  }

  const threshold = parsed.data.threshold;
  const active = iterParam ? Number(iterParam) : null;

  return (
    <div className="flex flex-col gap-3">
      {parsed.data.iterations.map((iteration) => {
        const accepted =
          threshold != null && iteration.score != null && iteration.score >= threshold;
        const selected = active === iteration.iter_index;
        return (
          <button
            key={iteration.iter_index}
            type="button"
            onClick={() => setIterParam(String(iteration.iter_index))}
            className={cn(
              "rounded-lg border border-border bg-bg-1 p-3 text-left transition-colors hover:border-border-strong",
              selected && "border-accent ring-1 ring-[--color-accent-dim]",
            )}
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="font-mono text-[12px] text-muted">
                iter {iteration.iter_index + 1}
              </div>
              <div
                className={cn(
                  "font-mono text-[12px]",
                  accepted ? "text-[--color-ok]" : "text-[--color-warn]",
                )}
              >
                {iteration.score != null ? iteration.score.toFixed(3) : "-"}
              </div>
            </div>
            <div className="mb-2">
              <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-2">
                Generated
              </div>
              <MarkdownView value={iteration.text ?? ""} />
            </div>
            <div
              className={cn(
                "rounded border px-2 py-1 text-[12px]",
                accepted
                  ? "border-[--color-ok-dim] bg-[--color-ok-dim]/30 text-[--color-ok]"
                  : "border-[--color-warn-dim] bg-[--color-warn-dim]/30 text-[--color-warn]",
              )}
            >
              {accepted ? "Accept" : "Reject"}{" "}
              {threshold != null
                ? `(${accepted ? ">=" : "<"} threshold ${threshold.toFixed(3)})`
                : ""}
            </div>
          </button>
        );
      })}
    </div>
  );
}
