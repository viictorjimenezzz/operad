import {
  DefinitionSection,
  ReproducibilitySection,
} from "@/components/agent-view/overview/definition-section";
import { IOHero } from "@/components/agent-view/overview/io-hero";
import { NotesSection } from "@/components/agent-view/overview/notes-section";
import { RunStatusStrip } from "@/components/agent-view/overview/run-status-strip";
import { EmptyState } from "@/components/ui";
import { useRunInvocations, useRunSummary } from "@/hooks/use-runs";
import { useParams } from "react-router-dom";

export function SingleInvocationOverviewTab() {
  const { runId } = useParams<{ runId: string }>();
  const summary = useRunSummary(runId);
  const invocations = useRunInvocations(runId);

  if (!runId) return null;
  if (summary.isLoading || invocations.isLoading) {
    return (
      <div className="h-full overflow-auto p-4">
        <div className="h-11 animate-pulse rounded-lg bg-bg-2" />
      </div>
    );
  }
  if (!summary.data) {
    return (
      <div className="flex h-full items-center justify-center">
        <EmptyState title="run not found" description="the invocation summary is unavailable" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-4 p-4">
        <RunStatusStrip
          dataSummary={summary.data}
          dataInvocations={invocations.data}
          runId={runId}
        />
        <IOHero dataSummary={summary.data} dataInvocations={invocations.data} runId={runId} />
        <NotesSection dataSummary={summary.data} runId={runId} />
        <DefinitionSection
          dataSummary={summary.data}
          dataInvocations={invocations.data}
          runId={runId}
        />
        <ReproducibilitySection
          dataSummary={summary.data}
          dataInvocations={invocations.data}
          runId={runId}
        />
      </div>
    </div>
  );
}
