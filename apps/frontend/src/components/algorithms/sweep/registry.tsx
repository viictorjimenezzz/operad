import { SweepCellsTab } from "@/components/algorithms/sweep/sweep-cells-tab";
import {
  SweepCostTab,
  SweepDetailOverview,
} from "@/components/algorithms/sweep/sweep-detail-overview";
import { SweepHeatmapTab } from "@/components/algorithms/sweep/sweep-heatmap-tab";
import { SweepParallelCoordsTab } from "@/components/algorithms/sweep/parallel-coords-tab";
import { SweepBestCellCard } from "@/components/charts/sweep-best-cell-card";
import { SweepCostTotalizer } from "@/components/charts/sweep-cost-totalizer";
import { SweepHeatmap } from "@/components/charts/sweep-heatmap";
import type { ComponentRegistry } from "@json-render/react";

export const sweepRegistry: ComponentRegistry = {
  SweepDetailOverview: ({ element }) => {
    const p = element.props as { data?: unknown; dataSummary?: unknown; dataChildren?: unknown };
    return (
      <SweepDetailOverview
        data={p.data}
        dataSummary={p.dataSummary}
        dataChildren={p.dataChildren}
      />
    );
  },
  SweepHeatmapTab: ({ element }) => {
    const p = element.props as { data?: unknown; dataChildren?: unknown };
    return <SweepHeatmapTab data={p.data} dataChildren={p.dataChildren} />;
  },
  SweepCellsTab: ({ element }) => {
    const p = element.props as { data?: unknown; dataChildren?: unknown; runId?: string };
    return <SweepCellsTab data={p.data} dataChildren={p.dataChildren} runId={p.runId ?? ""} />;
  },
  SweepCostTab: ({ element }) => {
    const p = element.props as { data?: unknown; dataChildren?: unknown };
    return <SweepCostTab data={p.data} dataChildren={p.dataChildren} />;
  },
  SweepParallelCoordsTab: ({ element }) => {
    const p = element.props as { data?: unknown; dataChildren?: unknown };
    return <SweepParallelCoordsTab data={p.data} dataChildren={p.dataChildren} />;
  },
  SweepHeatmap: ({ element }) => <SweepHeatmap data={(element.props as { data?: unknown }).data} />,
  SweepBestCellCard: ({ element }) => (
    <SweepBestCellCard data={(element.props as { data?: unknown }).data} />
  ),
  SweepCostTotalizer: ({ element }) => (
    <SweepCostTotalizer data={(element.props as { data?: unknown }).data} />
  ),
};
