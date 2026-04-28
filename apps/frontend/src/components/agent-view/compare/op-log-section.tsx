import { CompareRunColumn } from "@/components/agent-view/compare/compare-run-column";
import { CompareSection } from "@/components/agent-view/compare/compare-section";
import type { CompareRun } from "@/components/agent-view/compare/types";

export function OpLogSection({ runs }: { runs: CompareRun[] }) {
  return (
    <CompareSection title="Op Log">
      <div
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${Math.max(1, runs.length)}, minmax(0, 1fr))` }}
      >
        {runs.map((run) => (
          <CompareRunColumn key={run.runId} run={run}>
            {run.ops.length === 0 ? (
              <div className="text-[11px] text-muted">no typed mutations recorded</div>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {run.ops.map((op, index) => (
                  <li
                    key={`${run.runId}:op:${index}`}
                    className="rounded border border-border bg-bg-2 px-2 py-1 font-mono text-[10px] text-text"
                  >
                    {op}
                  </li>
                ))}
              </ul>
            )}
          </CompareRunColumn>
        ))}
      </div>
    </CompareSection>
  );
}
