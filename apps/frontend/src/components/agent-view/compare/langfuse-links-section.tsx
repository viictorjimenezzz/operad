import { CompareRunColumn } from "@/components/agent-view/compare/compare-run-column";
import { CompareSection } from "@/components/agent-view/compare/compare-section";
import type { CompareRun } from "@/components/agent-view/compare/types";

export function LangfuseLinksSection({ runs }: { runs: CompareRun[] }) {
  return (
    <CompareSection title="Langfuse Links">
      <div
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${Math.max(1, runs.length)}, minmax(0, 1fr))` }}
      >
        {runs.map((run) => (
          <CompareRunColumn key={run.runId} run={run}>
            {run.langfuseUrl ? (
              <a
                href={run.langfuseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex text-[11px] text-accent hover:text-[--color-accent-strong]"
              >
                open trace
              </a>
            ) : (
              <div className="text-[11px] text-muted">no langfuse trace</div>
            )}
          </CompareRunColumn>
        ))}
      </div>
    </CompareSection>
  );
}
