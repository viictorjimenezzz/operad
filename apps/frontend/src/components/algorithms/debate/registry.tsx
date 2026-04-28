import { DebateDetailOverview } from "@/components/algorithms/debate/debate-detail-overview";
import {
  DebateConsensusTab,
  DebateRoundsTab,
} from "@/components/algorithms/debate/debate-rounds-tab";
import { DebateTranscript } from "@/components/charts/debate-transcript";
import type { ComponentRegistry } from "@json-render/react";

export const debateRegistry: ComponentRegistry = {
  DebateDetailOverview: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataDebate?: unknown;
      dataChildren?: unknown;
      runId?: string;
    };
    return (
      <DebateDetailOverview
        dataSummary={p.dataSummary}
        dataDebate={p.dataDebate}
        dataChildren={p.dataChildren}
      />
    );
  },
  DebateRoundsTab: ({ element }) => {
    const p = element.props as { data?: unknown };
    return <DebateRoundsTab data={p.data} />;
  },
  DebateTranscriptTab: ({ element }) => {
    const p = element.props as { data?: unknown };
    return (
      <div className="h-full overflow-auto p-4">
        <DebateTranscript data={p.data} />
      </div>
    );
  },
  DebateConsensusTab: ({ element }) => {
    const p = element.props as { data?: unknown };
    return <DebateConsensusTab data={p.data} />;
  },
};
