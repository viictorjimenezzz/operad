import { BeamDetailOverview } from "@/components/algorithms/beam/beam-detail-overview";
import { BeamLeaderboardTab } from "@/components/algorithms/beam/leaderboard-tab";
import { BeamScoreHistogramTab } from "@/components/algorithms/beam/score-histogram-tab";
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
  BeamLeaderboard: ({ element }) => {
    const p = element.props as {
      data?: unknown;
      dataIterations?: unknown;
      dataChildren?: unknown;
      runId?: string;
    };
    return (
      <BeamLeaderboardTab
        data={p.data}
        dataIterations={p.dataIterations}
        dataChildren={p.dataChildren}
        runId={p.runId ?? ""}
      />
    );
  },
  BeamScoreHistogram: ({ element }) => {
    const p = element.props as { data?: unknown; dataIterations?: unknown; bins?: number };
    return <BeamScoreHistogramTab data={p.data} dataIterations={p.dataIterations} bins={p.bins} />;
  },
  CriticRationaleCard: ({ element }) => {
    const p = element.props as ComponentProps<typeof CriticRationaleCard>;
    return <CriticRationaleCard {...p} />;
  },
  BeamCandidateChart: ({ element }) => {
    const p = element.props as {
      data?: unknown;
      iterationsData?: unknown;
      dataIterations?: unknown;
      height?: number;
    };
    return (
      <BeamCandidateChart
        data={p.data}
        iterationsData={p.dataIterations ?? p.iterationsData}
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
