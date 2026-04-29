import { EvoAgentInvocationsTab } from "@/components/algorithms/evogradient/evo-agent-invocations-tab";
import { EvoBestDiffTab } from "@/components/algorithms/evogradient/evo-bestdiff-tab";
import { EvoDetailOverview } from "@/components/algorithms/evogradient/evo-detail-overview";
import { EvoEvolutionTab } from "@/components/algorithms/evogradient/evo-evolution-tab";
import { EvoLineageTab } from "@/components/algorithms/evogradient/evo-lineage-tab";
import { EvoOperatorsTab } from "@/components/algorithms/evogradient/evo-operators-tab";
import { EvoParametersTab } from "@/components/algorithms/evogradient/evo-parameters-tab";
import { EvoPopulationTab } from "@/components/algorithms/evogradient/evo-population-tab";
import { FitnessCurve } from "@/components/charts/fitness-curve";
import { GradientLog } from "@/components/charts/gradient-log";
import { MutationHeatmap } from "@/components/charts/mutation-heatmap";
import { OpSuccessTable } from "@/components/charts/op-success-table";
import { PopulationScatter } from "@/components/charts/population-scatter";
import type { ComponentRegistry } from "@json-render/react";

export const evoGradientRegistry: ComponentRegistry = {
  EvoDetailOverview: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataFitness?: unknown;
      dataMutations?: unknown;
      dataEvents?: unknown;
    };
    return (
      <EvoDetailOverview
        summary={p.dataSummary}
        fitness={p.dataFitness}
        mutations={p.dataMutations}
        events={p.dataEvents}
      />
    );
  },
  EvoEvolutionTab: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataFitness?: unknown;
      dataEvents?: unknown;
    };
    return (
      <EvoEvolutionTab summary={p.dataSummary} fitness={p.dataFitness} events={p.dataEvents} />
    );
  },
  EvoPopulationTab: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataFitness?: unknown;
      dataEvents?: unknown;
    };
    return (
      <EvoPopulationTab summary={p.dataSummary} fitness={p.dataFitness} events={p.dataEvents} />
    );
  },
  EvoOperatorsTab: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataMutations?: unknown;
      dataEvents?: unknown;
    };
    return (
      <EvoOperatorsTab summary={p.dataSummary} mutations={p.dataMutations} events={p.dataEvents} />
    );
  },
  EvoLineageTab: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataFitness?: unknown;
      dataEvents?: unknown;
    };
    return <EvoLineageTab summary={p.dataSummary} fitness={p.dataFitness} events={p.dataEvents} />;
  },
  EvoBestDiffTab: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataFitness?: unknown;
      dataEvents?: unknown;
    };
    return <EvoBestDiffTab summary={p.dataSummary} fitness={p.dataFitness} events={p.dataEvents} />;
  },
  EvoParametersTab: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataFitness?: unknown;
      dataEvents?: unknown;
    };
    return (
      <EvoParametersTab summary={p.dataSummary} fitness={p.dataFitness} events={p.dataEvents} />
    );
  },
  EvoAgentInvocationsTab: ({ element }) => {
    const p = element.props as { runId?: string };
    return <EvoAgentInvocationsTab runId={p.runId ?? ""} />;
  },
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
