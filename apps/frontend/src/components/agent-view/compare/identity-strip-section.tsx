import { CompareRunColumn } from "@/components/agent-view/compare/compare-run-column";
import { CompareSection } from "@/components/agent-view/compare/compare-section";
import type { CompareRun } from "@/components/agent-view/compare/types";
import { ValuePreview } from "@/components/agent-view/compare/value-preview";
import { HashRow } from "@/components/ui";

export function IdentityStripSection({ runs }: { runs: CompareRun[] }) {
  const reference = runs[0] ?? null;
  return (
    <CompareSection title="Identity Strip">
      <div
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${Math.max(1, runs.length)}, minmax(0, 1fr))` }}
      >
        {runs.map((run) => (
          <CompareRunColumn key={run.runId} run={run}>
            <div className="text-[11px]">
              <div className="text-muted">agent path</div>
              <div className="font-mono text-text">{run.summary.root_agent_path ?? "—"}</div>
            </div>
            <HashRow current={run.hashes} previous={reference?.hashes} />
            <div className="space-y-1">
              <div className="text-[10px] uppercase tracking-[0.06em] text-muted">Input</div>
              <ValuePreview value={run.latestInvocation?.input ?? null} />
            </div>
            <div className="space-y-1">
              <div className="text-[10px] uppercase tracking-[0.06em] text-muted">Output</div>
              <ValuePreview value={run.latestInvocation?.output ?? null} />
            </div>
          </CompareRunColumn>
        ))}
      </div>
    </CompareSection>
  );
}
