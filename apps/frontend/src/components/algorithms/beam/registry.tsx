import { BeamDetailOverview } from "@/components/algorithms/beam/beam-detail-overview";
import { BeamLeaderboardTab } from "@/components/algorithms/beam/leaderboard-tab";
import { BeamMetricsTab } from "@/components/algorithms/beam/metrics-tab";
import { CriticRationaleCard } from "@/components/algorithms/beam/critic-rationale-card";
import { BeamCandidateChart } from "@/components/charts/beam-candidate-chart";
import { ConvergenceCurve } from "@/components/charts/convergence-curve";
import { IterationProgression } from "@/components/charts/iteration-progression";
import type { ComponentRegistry } from "@json-render/react";
import type { ComponentProps } from "react";

export const beamRegistry: ComponentRegistry = {
  BeamDetailOverview: ({ element }) => {
    const p = element.props as {
      dataSummary?: unknown;
      dataIterations?: unknown;
      dataChildren?: unknown;
    };
    return (
      <BeamDetailOverview
        dataSummary={p.dataSummary}
        dataIterations={p.dataIterations}
        dataChildren={p.dataChildren}
      />
    );
  },
  BeamLeaderboardTab: ({ element }) => {
    const p = element.props as {
      data?: unknown;
      dataIterations?: unknown;
      dataChildren?: unknown;
      dataAgentsSummary?: unknown;
      runId?: string;
    };
    return (
      <BeamLeaderboardTab
        data={p.data}
        dataIterations={p.dataIterations}
        dataChildren={p.dataChildren}
        dataAgentsSummary={p.dataAgentsSummary}
        runId={p.runId ?? ""}
      />
    );
  },
  CriticRationaleCard: ({ element }) => {
    const p = element.props as ComponentProps<typeof CriticRationaleCard>;
    return <CriticRationaleCard {...p} />;
  },
  BeamCandidatesTab: ({ element }) => {
    const p = element.props as {
      data?: unknown;
      iterationsData?: unknown;
      dataIterations?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
      dataAgentsSummary?: unknown;
      runId?: string;
      height?: number;
    };
    return (
      <BeamCandidateChart
        data={p.data}
        iterationsData={p.dataIterations ?? p.iterationsData}
        dataEvents={p.dataEvents}
        dataChildren={p.dataChildren}
        dataAgentsSummary={p.dataAgentsSummary}
        height={p.height ?? 220}
        {...(p.runId !== undefined ? { runId: p.runId } : {})}
      />
    );
  },
  BeamMetricsTab: ({ element }) => {
    const p = element.props as {
      data?: unknown;
      dataIterations?: unknown;
      dataEvents?: unknown;
      dataChildren?: unknown;
      dataAgentsSummary?: unknown;
    };
    return (
      <BeamMetricsTab
        data={p.data}
        dataIterations={p.dataIterations}
        dataEvents={p.dataEvents}
        dataChildren={p.dataChildren}
        dataAgentsSummary={p.dataAgentsSummary}
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
