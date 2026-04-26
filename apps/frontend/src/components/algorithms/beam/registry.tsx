import { BeamCandidateChart } from "@/components/charts/beam-candidate-chart";
import { ConvergenceCurve } from "@/components/charts/convergence-curve";
import { IterationProgression } from "@/components/charts/iteration-progression";
import type { ComponentRegistry } from "@json-render/react";

export const beamRegistry: ComponentRegistry = {
  BeamCandidateChart: ({ element }) => {
    const p = element.props as {
      data?: unknown;
      iterationsData?: unknown;
      height?: number;
    };
    return (
      <BeamCandidateChart
        data={p.data}
        iterationsData={p.iterationsData}
        height={p.height ?? 220}
      />
    );
  },
  ConvergenceCurve: ({ element }) => {
    const p = element.props as { data?: unknown; height?: number };
    return <ConvergenceCurve data={p.data} height={p.height ?? 220} />;
  },
  IterationProgression: ({ element }) => {
    const p = element.props as { data?: unknown; phaseFilter?: string; showDiff?: boolean };
    return (
      <IterationProgression
        data={p.data}
        {...(p.phaseFilter !== undefined ? { phaseFilter: p.phaseFilter } : {})}
        {...(p.showDiff !== undefined ? { showDiff: p.showDiff } : {})}
      />
    );
  },
};
