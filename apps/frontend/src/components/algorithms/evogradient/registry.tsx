import { FitnessCurve } from "@/components/charts/fitness-curve";
import { GradientLog } from "@/components/charts/gradient-log";
import { MutationHeatmap } from "@/components/charts/mutation-heatmap";
import { OpSuccessTable } from "@/components/charts/op-success-table";
import { PopulationScatter } from "@/components/charts/population-scatter";
import type { ComponentRegistry } from "@json-render/react";

export const evoGradientRegistry: ComponentRegistry = {
  FitnessCurve: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <FitnessCurve data={p.data} height={p.height ?? 220} />;
  },
  PopulationScatter: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <PopulationScatter data={p.data} height={p.height ?? 220} />;
  },
  MutationHeatmap: ({ element }) => (
    <MutationHeatmap data={(element.props as { data?: unknown }).data} />
  ),
  OpSuccessTable: ({ element }) => (
    <OpSuccessTable data={(element.props as { data?: unknown }).data} />
  ),
  GradientLog: ({ element }) => <GradientLog data={(element.props as { data?: unknown }).data} />,
};
