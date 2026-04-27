import { IterationLadder } from "@/components/algorithms/selfrefine/iteration-ladder";
import { SelfRefineDetailOverview } from "@/components/algorithms/selfrefine/selfrefine-detail-overview";
import { ConvergenceCurve } from "@/components/charts/convergence-curve";
import type { ComponentRegistry } from "@json-render/react";

export const selfRefineRegistry: ComponentRegistry = {
  SelfRefineDetailOverview: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataIterations?: unknown;
      dataChildren?: unknown;
    };
    return (
      <SelfRefineDetailOverview
        dataSummary={p.dataSummary}
        dataIterations={p.dataIterations}
        dataChildren={p.dataChildren}
      />
    );
  },
  IterationLadder: ({ element }) => {
    const p = element.props as { data?: unknown; dataChildren?: unknown };
    return <IterationLadder data={p.data} dataChildren={p.dataChildren} />;
  },
  SelfRefineConvergence: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <ConvergenceCurve data={p.data} height={p.height ?? 260} />;
  },
};
