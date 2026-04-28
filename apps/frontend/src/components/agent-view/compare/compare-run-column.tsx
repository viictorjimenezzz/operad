import type { CompareRun } from "@/components/agent-view/compare/types";
import { hashColor } from "@/lib/hash-color";
import { truncateMiddle } from "@/lib/utils";
import type { ReactNode } from "react";

export function CompareRunColumn({
  run,
  children,
}: {
  run: CompareRun;
  children: ReactNode;
}) {
  const className =
    run.summary.algorithm_class ?? run.summary.root_agent_path?.split(".").at(-1) ?? "run";

  return (
    <article data-compare-run={run.runId} className="min-w-0 border border-border bg-bg-1">
      <div className="h-1 w-full" style={{ background: hashColor(run.hashContent) }} />
      <div className="border-b border-border px-2 py-1.5">
        <div className="font-mono text-[11px] text-text">{truncateMiddle(run.runId, 18)}</div>
        <div className="text-[10px] text-muted">{className}</div>
      </div>
      <div className="space-y-2 px-2 py-2">{children}</div>
    </article>
  );
}
