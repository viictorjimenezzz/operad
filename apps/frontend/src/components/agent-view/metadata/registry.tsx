import { AgentMetadataPanel } from "@/components/agent-view/metadata/agent-metadata-panel";
import type { AgentInvocationsResponse, RunSummary } from "@/lib/types";
import type { ComponentRegistry } from "@json-render/react";

export const metadataDefinitions = {} as const;

export const metadataComponents: ComponentRegistry = {
  AgentMetadataPanel: ({ element }) => {
    const p = element.props as {
      dataSummary?: RunSummary;
      dataInvocations?: AgentInvocationsResponse;
      runId?: string;
    };
    return (
      <AgentMetadataPanel summary={p.dataSummary} invocations={p.dataInvocations} runId={p.runId} />
    );
  },
};
