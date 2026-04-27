import { DecisionsView } from "@/components/algorithms/talker_reasoner/decisions-view";
import { TalkerTreeTab } from "@/components/algorithms/talker_reasoner/scenario-tree-view";
import { TalkerDetailOverview } from "@/components/algorithms/talker_reasoner/talker-detail-overview";
import { TranscriptView } from "@/components/algorithms/talker_reasoner/transcript-view";
import type { ComponentRegistry } from "@json-render/react";

export const talkerReasonerRegistry: ComponentRegistry = {
  TalkerDetailOverview: ({ element }) => {
    const p = element.props as { dataSummary?: unknown; dataEvents?: unknown };
    return <TalkerDetailOverview summary={p.dataSummary} events={p.dataEvents} />;
  },
  TalkerTreeTab: ({ element }) => {
    const p = element.props as { dataSummary?: unknown; dataEvents?: unknown };
    return <TalkerTreeTab summary={p.dataSummary} events={p.dataEvents} />;
  },
  TranscriptView: ({ element }) => {
    const p = element.props as { dataSummary?: unknown; dataEvents?: unknown };
    return <TranscriptView summary={p.dataSummary} events={p.dataEvents} />;
  },
  DecisionsView: ({ element }) => {
    const p = element.props as {
      runId?: string;
      dataSummary?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
    };
    return (
      <DecisionsView
        runId={p.runId ?? ""}
        summary={p.dataSummary}
        events={p.dataEvents}
        childRuns={p.dataChildren}
      />
    );
  },
};
