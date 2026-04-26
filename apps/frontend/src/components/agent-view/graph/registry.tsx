import { InteractiveGraph } from "@/components/agent-view/graph/interactive-graph";
import type { IoGraphResponse } from "@/lib/types";
import type { ComponentRegistry } from "@json-render/react";

export const graphDefinitions = {} as const;

export const graphComponents: ComponentRegistry = {
  InteractiveGraph: ({ element }) => {
    const p = element.props as {
      dataIoGraph?: IoGraphResponse;
      runId: string;
    };
    return <InteractiveGraph ioGraph={p.dataIoGraph} runId={p.runId} />;
  },
};
