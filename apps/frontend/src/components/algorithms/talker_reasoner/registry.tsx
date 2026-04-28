import { TalkerDecisionsTab } from "@/components/algorithms/talker_reasoner/decisions-tab";
import { TalkerTranscriptTab } from "@/components/algorithms/talker_reasoner/transcript-tab";
import { TalkerTreeTab } from "@/components/algorithms/talker_reasoner/tree-tab";
import type { ComponentRegistry } from "@json-render/react";

export const talkerReasonerRegistry: ComponentRegistry = {
  TalkerTreeTab: ({ element }) => {
    const p = element.props as { dataSummary?: unknown; dataEvents?: unknown };
    return <TalkerTreeTab dataSummary={p.dataSummary} dataEvents={p.dataEvents} />;
  },
  TalkerTranscriptTab: ({ element }) => {
    const p = element.props as { dataSummary?: unknown; dataEvents?: unknown };
    return <TalkerTranscriptTab dataSummary={p.dataSummary} dataEvents={p.dataEvents} />;
  },
  TalkerDecisionsTab: ({ element }) => {
    const p = element.props as { runId?: string; dataSummary?: unknown; dataEvents?: unknown };
    return (
      <TalkerDecisionsTab runId={p.runId} dataSummary={p.dataSummary} dataEvents={p.dataEvents} />
    );
  },
};
