import { Shell } from "@/dashboard/Shell";
import { AgentGroupOverviewTab, AgentGroupPage } from "@/dashboard/pages/AgentGroupPage";
import {
  AgentGroupGraphTab,
  AgentGroupMetricsTab,
  AgentGroupRunsTab,
  AgentGroupTrainTab,
} from "@/dashboard/pages/AgentGroupSubpages";
import { AgentsIndexPage } from "@/dashboard/pages/AgentsIndexPage";
import { AlgorithmsIndexPage } from "@/dashboard/pages/AlgorithmsIndexPage";
import { BenchmarkDetailPage } from "@/dashboard/pages/BenchmarkDetailPage";
import { BenchmarksPage } from "@/dashboard/pages/BenchmarksPage";
import { CassetteDetailPage } from "@/dashboard/pages/CassetteDetailPage";
import { CassettesPage } from "@/dashboard/pages/CassettesPage";
import { ExperimentsPage } from "@/dashboard/pages/ExperimentsPage";
import { NotFoundPage } from "@/dashboard/pages/NotFoundPage";
import { OPROIndexPage } from "@/dashboard/pages/OPROIndexPage";
import { TrainingIndexPage } from "@/dashboard/pages/TrainingIndexPage";
import { PrimitivesGallery } from "@/dashboard/pages/__dev/PrimitivesGallery";
import { AgentRunDetailLayout } from "@/dashboard/pages/run-detail/AgentRunDetailLayout";
import { AlgorithmDetailLayout } from "@/dashboard/pages/run-detail/AlgorithmDetailLayout";
import { DriftTab } from "@/dashboard/pages/run-detail/DriftTab";
import { GraphTab } from "@/dashboard/pages/run-detail/GraphTab";
import { MetricsTab } from "@/dashboard/pages/run-detail/MetricsTab";
import { OverviewTab } from "@/dashboard/pages/run-detail/OverviewTab";
import { TrainingDetailLayout } from "@/dashboard/pages/run-detail/TrainingDetailLayout";
import { Navigate, createBrowserRouter, useRouteError } from "react-router-dom";

export const dashboardRoutes = [
  {
    path: "/",
    element: <Shell />,
    children: [
      // Default landing -> agents.
      { index: true, element: <Navigate to="/agents" replace /> },

      // Agents rail.
      { path: "agents", element: <AgentsIndexPage /> },
      {
        path: "agents/:hashContent",
        element: <AgentGroupPage />,
        children: [
          { index: true, element: <AgentGroupOverviewTab /> },
          { path: "runs", element: <AgentGroupRunsTab /> },
          { path: "metrics", element: <AgentGroupMetricsTab /> },
          { path: "train", element: <AgentGroupTrainTab /> },
          { path: "graph", element: <AgentGroupGraphTab /> },
        ],
      },
      {
        path: "agents/:hashContent/runs/:runId",
        element: <AgentRunDetailLayout />,
        children: [
          { index: true, element: <OverviewTab /> },
          { path: "graph", element: <GraphTab />, errorElement: <GraphRouteErrorBoundary /> },
          { path: "metrics", element: <MetricsTab /> },
          { path: "drift", element: <DriftTab /> },
        ],
      },

      // Algorithms rail.
      { path: "algorithms", element: <AlgorithmsIndexPage /> },
      {
        path: "algorithms/:runId",
        element: <AlgorithmDetailLayout />,
      },

      // Training rail.
      { path: "training", element: <TrainingIndexPage /> },
      {
        path: "training/:runId",
        element: <TrainingDetailLayout />,
      },

      // OPRO rail.
      { path: "opro", element: <OPROIndexPage /> },
      { path: "opro/:runId", element: <AlgorithmDetailLayout /> },

      // Other rails.
      { path: "benchmarks", element: <BenchmarksPage /> },
      { path: "benchmarks/:benchmarkId", element: <BenchmarkDetailPage /> },
      { path: "cassettes", element: <CassettesPage /> },
      { path: "cassettes/*", element: <CassetteDetailPage /> },
      { path: "experiments", element: <ExperimentsPage /> },
      ...(import.meta.env.DEV
        ? [{ path: "__dev/primitives", element: <PrimitivesGallery /> }]
        : []),
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const dashboardRouter = createBrowserRouter(dashboardRoutes);

function GraphRouteErrorBoundary() {
  const error = useRouteError();
  const message = error instanceof Error ? error.message : "unknown graph rendering error";

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-md rounded-lg border border-[--color-err-dim] bg-bg-1 p-5">
        <div className="text-[14px] font-medium text-text">Graph failed to render</div>
        <div className="mt-2 text-[12px] leading-5 text-muted">
          The rest of the run is still available. Collapse the graph or reload after fixing the
          graph payload.
        </div>
        <pre className="mt-3 max-h-32 overflow-auto rounded-md bg-bg-inset p-2 font-mono text-[11px] text-[--color-err]">
          {message}
        </pre>
      </div>
    </div>
  );
}
