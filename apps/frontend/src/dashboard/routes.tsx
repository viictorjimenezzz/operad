import { Shell } from "@/dashboard/Shell";
import { AgentGroupGraphTab } from "@/dashboard/pages/AgentGroupGraphTab";
import { AgentGroupMetricsTab } from "@/dashboard/pages/AgentGroupMetricsTab";
import { AgentGroupOverviewTab } from "@/dashboard/pages/AgentGroupOverviewTab";
import { AgentGroupPage } from "@/dashboard/pages/AgentGroupPage";
import { AgentGroupRunsTab } from "@/dashboard/pages/AgentGroupRunsTab";
import { AgentGroupTrainTab } from "@/dashboard/pages/AgentGroupTrainTab";
import { AgentsByClassPage } from "@/dashboard/pages/AgentsByClassPage";
import { AgentsIndexPage } from "@/dashboard/pages/AgentsIndexPage";
import { AlgorithmsIndexPage } from "@/dashboard/pages/AlgorithmsIndexPage";
import { ArchivePage } from "@/dashboard/pages/ArchivePage";
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
import { SingleInvocationDriftTab } from "@/dashboard/pages/run-detail/SingleInvocationDriftTab";
import { SingleInvocationGraphTab } from "@/dashboard/pages/run-detail/SingleInvocationGraphTab";
import { SingleInvocationMetricsTab } from "@/dashboard/pages/run-detail/SingleInvocationMetricsTab";
import { SingleInvocationOverviewTab } from "@/dashboard/pages/run-detail/SingleInvocationOverviewTab";
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
      { path: "agents/_class_/:className", element: <AgentsByClassPage /> },
      {
        path: "agents/:hashContent",
        element: <AgentGroupPage />,
        children: [
          { index: true, element: <AgentGroupOverviewTab /> },
          { path: "invocations", element: <AgentGroupRunsTab /> },
          { path: "metrics", element: <AgentGroupMetricsTab /> },
          { path: "training", element: <AgentGroupTrainTab /> },
          {
            path: "graph",
            element: <AgentGroupGraphTab />,
            errorElement: <GraphRouteErrorBoundary />,
          },
          // Legacy aliases — old links/bookmarks should not 404.
          {
            path: "runs",
            element: <Navigate to="../invocations" relative="path" replace />,
          },
          {
            path: "train",
            element: <Navigate to="../training" relative="path" replace />,
          },
        ],
      },
      {
        path: "agents/:hashContent/runs/:runId",
        element: <AgentRunDetailLayout />,
        children: [
          { index: true, element: <SingleInvocationOverviewTab /> },
          {
            path: "graph",
            element: <SingleInvocationGraphTab />,
            errorElement: <GraphRouteErrorBoundary />,
          },
          { path: "metrics", element: <SingleInvocationMetricsTab /> },
          { path: "drift", element: <SingleInvocationDriftTab /> },
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
      { path: "archive", element: <ArchivePage /> },
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
        <div className="text-[14px] font-medium text-text">Graph unavailable</div>
        <div className="mt-2 text-[12px] leading-5 text-muted">
          The rest of the run is still available. The graph view will recover when a valid payload
          is available.
        </div>
        <pre className="mt-3 max-h-32 overflow-auto rounded-md bg-bg-inset p-2 font-mono text-[11px] text-[--color-err]">
          {message}
        </pre>
      </div>
    </div>
  );
}
