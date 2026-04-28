import {
  SelfRefineIterationsTab,
  SelfRefineLadderTab,
} from "@/components/algorithms/selfrefine/refine-ladder-tab";
import type { ComponentRegistry } from "@json-render/react";

export const selfRefineRegistry: ComponentRegistry = {
  SelfRefineLadderTab: ({ element }) => {
    const p = element.props as {
      dataIterations?: unknown;
    };
    return <SelfRefineLadderTab dataIterations={p.dataIterations} />;
  },
  SelfRefineIterationsTab: ({ element }) => {
    const p = element.props as {
      dataIterations?: unknown;
      runId?: string;
    };
    return (
      <SelfRefineIterationsTab
        dataIterations={p.dataIterations}
        {...(p.runId ? { runId: p.runId } : {})}
      />
    );
  },
};
