import { SweepBestCellCard } from "@/components/charts/sweep-best-cell-card";
import { SweepCostTotalizer } from "@/components/charts/sweep-cost-totalizer";
import { SweepHeatmap } from "@/components/charts/sweep-heatmap";
import type { ComponentRegistry } from "@json-render/react";

export const sweepRegistry: ComponentRegistry = {
  SweepHeatmap: ({ element }) => <SweepHeatmap data={(element.props as { data?: unknown }).data} />,
  SweepBestCellCard: ({ element }) => (
    <SweepBestCellCard data={(element.props as { data?: unknown }).data} />
  ),
  SweepCostTotalizer: ({ element }) => (
    <SweepCostTotalizer data={(element.props as { data?: unknown }).data} />
  ),
};
