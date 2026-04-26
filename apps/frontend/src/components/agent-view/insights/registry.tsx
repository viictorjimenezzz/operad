import { AgentInsightsRow } from "@/components/agent-view/insights/agent-insights-row";
import { ValueDistribution } from "@/components/agent-view/insights/value-distribution";
import type { ComponentRegistry } from "@json-render/react";

export const insightsDefinitions = {} as const;
export const insightsComponents: ComponentRegistry = {
  AgentInsightsRow: ({ element }) => {
    const props = element.props as {
      summary?: unknown;
      invocations?: unknown;
      runId?: string | null;
      dataSummary?: unknown;
      dataInvocations?: unknown;
    };
    return (
      <AgentInsightsRow
        {...(props.summary !== undefined ? { summary: props.summary } : {})}
        {...(props.invocations !== undefined ? { invocations: props.invocations } : {})}
        {...(props.runId !== undefined ? { runId: props.runId } : {})}
        {...(props.dataSummary !== undefined ? { dataSummary: props.dataSummary } : {})}
        {...(props.dataInvocations !== undefined ? { dataInvocations: props.dataInvocations } : {})}
      />
    );
  },
  ValueDistribution: ({ element }) => {
    const props = element.props as { label?: string; data?: unknown[]; agentPath?: string; side?: "in" | "out" };
    return (
      <ValueDistribution
        label={props.label ?? "values"}
        values={Array.isArray(props.data) ? props.data : []}
        {...(props.agentPath !== undefined ? { agentPath: props.agentPath } : {})}
        {...(props.side !== undefined ? { side: props.side } : {})}
      />
    );
  },
};
