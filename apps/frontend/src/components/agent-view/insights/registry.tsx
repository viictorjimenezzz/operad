import { AgentInsightsRow } from "@/components/agent-view/insights/agent-insights-row";
import type { AgentInvocationsResponse, RunSummary } from "@/lib/types";
import type { ComponentRegistry } from "@json-render/react";

export const insightsDefinitions = {} as const;

export const insightsComponents: ComponentRegistry = {
  AgentInsightsRow: ({ element }) => {
    const p = element.props as {
      dataSummary?: RunSummary;
      dataInvocations?: AgentInvocationsResponse;
    };
    return <AgentInsightsRow summary={p.dataSummary} invocations={p.dataInvocations} />;
  },
};
