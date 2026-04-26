import { AgentGraph } from "@/components/charts/agent-graph";
import type { ComponentRegistry } from "@json-render/react";

export const chartsRegistry: ComponentRegistry = {
  AgentGraph: ({ element }) => {
    const p = element.props as { data?: unknown; dataMutations?: unknown };
    return <AgentGraph data={p.data} mutations={p.dataMutations} />;
  },
};
