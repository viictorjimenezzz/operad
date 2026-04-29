import { AgentsTab } from "@/components/agent-view/page-shell/agents-tab";
import { EventsTab } from "@/components/agent-view/page-shell/events-tab";
import { agentViewRegistry } from "@/components/agent-view/registry";
import { algorithmsRegistry } from "@/components/algorithms/registry";
import { chartsRegistry } from "@/components/charts/registry";
import { panelsRegistry } from "@/components/panels/registry";
import { uiRegistry } from "@/components/ui/registry";
import type { ComponentRegistry } from "@json-render/react";

export const registry: ComponentRegistry = {
  ...uiRegistry,
  ...panelsRegistry,
  ...chartsRegistry,
  ...algorithmsRegistry,
  ...agentViewRegistry,
  AgentsTab: ({ element }) => {
    const props = element.props as {
      runId?: string;
      mode?: "summary" | "invocations";
      dataEvents?: unknown;
      dataAgentsSummary?: unknown;
      groupBy?: "hash" | "none";
      extraColumns?: string[];
      emptyTitle?: string;
      emptyDescription?: string;
    };
    return (
      <AgentsTab
        runId={props.runId ?? ""}
        {...(props.mode ? { mode: props.mode } : {})}
        {...(props.dataEvents ? { dataEvents: props.dataEvents } : {})}
        {...(props.dataAgentsSummary ? { dataAgentsSummary: props.dataAgentsSummary } : {})}
        {...(props.groupBy ? { groupBy: props.groupBy } : {})}
        {...(props.extraColumns ? { extraColumns: props.extraColumns } : {})}
        {...(props.emptyTitle ? { emptyTitle: props.emptyTitle } : {})}
        {...(props.emptyDescription ? { emptyDescription: props.emptyDescription } : {})}
      />
    );
  },
  EventsTab: ({ element }) => {
    const props = element.props as {
      runId?: string;
      defaultKindFilter?: string[];
      defaultPathFilter?: string;
    };
    return (
      <EventsTab
        runId={props.runId ?? ""}
        {...(props.defaultKindFilter ? { defaultKindFilter: props.defaultKindFilter } : {})}
        {...(props.defaultPathFilter ? { defaultPathFilter: props.defaultPathFilter } : {})}
      />
    );
  },
};
