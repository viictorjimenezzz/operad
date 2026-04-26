import { DebateConsensusTracker } from "@/components/charts/debate-consensus-tracker";
import { DebateRoundView } from "@/components/charts/debate-round-view";
import { DebateTranscript } from "@/components/charts/debate-transcript";
import type { ComponentRegistry } from "@json-render/react";

export const debateRegistry: ComponentRegistry = {
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
