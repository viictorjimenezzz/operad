import { DebateDetailOverview } from "@/components/algorithms/debate/debate-detail-overview";
import {
  DebateConsensusTab,
  DebateRoundsTab,
} from "@/components/algorithms/debate/debate-rounds-tab";
import { DebateConsensusTracker } from "@/components/charts/debate-consensus-tracker";
import { DebateRoundView } from "@/components/charts/debate-round-view";
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
  DebateConsensusTab: ({ element }) => {
    const p = element.props as { data?: unknown };
    return <DebateConsensusTab data={p.data} />;
  },
  DebateRoundView: ({ element }) => (
    <DebateRoundView data={(element.props as { data?: unknown }).data} />
  ),
  DebateTranscript: ({ element }) => (
    <DebateTranscript data={(element.props as { data?: unknown }).data} />
  ),
  DebateConsensusTracker: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <DebateConsensusTracker data={p.data} height={p.height ?? 220} />;
  },
};
