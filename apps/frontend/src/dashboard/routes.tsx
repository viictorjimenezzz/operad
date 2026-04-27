import { Shell } from "@/dashboard/Shell";
import { AgentGroupOverviewTab, AgentGroupPage } from "@/dashboard/pages/AgentGroupPage";
import {
  AgentGroupCostTab,
  AgentGroupDriftTab,
  AgentGroupRunsTab,
} from "@/dashboard/pages/AgentGroupSubpages";
import { AgentsIndexPage } from "@/dashboard/pages/AgentsIndexPage";
import { AlgorithmsIndexPage } from "@/dashboard/pages/AlgorithmsIndexPage";
import { BenchmarkDetailPage } from "@/dashboard/pages/BenchmarkDetailPage";
import { BenchmarksPage } from "@/dashboard/pages/BenchmarksPage";
import { CassetteDetailPage } from "@/dashboard/pages/CassetteDetailPage";
import { CassettesPage } from "@/dashboard/pages/CassettesPage";
import { ExperimentsPage } from "@/dashboard/pages/ExperimentsPage";
import { NotFoundPage } from "@/dashboard/pages/NotFoundPage";
import { TrainingIndexPage } from "@/dashboard/pages/TrainingIndexPage";
import { PrimitivesGallery } from "@/dashboard/pages/__dev/PrimitivesGallery";
import { CostTab } from "@/dashboard/pages/run-detail/CostTab";
import { DriftTab } from "@/dashboard/pages/run-detail/DriftTab";
import { GraphTab } from "@/dashboard/pages/run-detail/GraphTab";
import { InvocationsTab } from "@/dashboard/pages/run-detail/InvocationsTab";
import { OverviewTab } from "@/dashboard/pages/run-detail/OverviewTab";
import { RunDetailLayout } from "@/dashboard/pages/run-detail/RunDetailLayout";
import { TrainTab } from "@/dashboard/pages/run-detail/TrainTab";
import { Navigate, createBrowserRouter, useRouteError } from "react-router-dom";

const runDetailChildren = [
  { index: true, element: <OverviewTab /> },
  { path: "graph", element: <GraphTab />, errorElement: <GraphRouteErrorBoundary /> },
  { path: "invocations", element: <InvocationsTab /> },
  { path: "train", element: <TrainTab /> },
  { path: "cost", element: <CostTab /> },
  { path: "drift", element: <DriftTab /> },
];

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
          { path: "cost", element: <AgentGroupCostTab /> },
          { path: "drift", element: <AgentGroupDriftTab /> },
        ],
      },
      {
        path: "agents/:hashContent/runs/:runId",
        element: <RunDetailLayout />,
        children: runDetailChildren,
      },

      // Algorithms rail.
      { path: "algorithms", element: <AlgorithmsIndexPage /> },
      {
        path: "algorithms/:runId",
        element: <RunDetailLayout />,
        children: runDetailChildren,
      },

      // Training rail.
      { path: "training", element: <TrainingIndexPage /> },
      {
        path: "training/:runId",
        element: <RunDetailLayout />,
        children: runDetailChildren,
      },

      // Legacy: /runs/:runId still resolves through the same layout.
      {
        path: "runs/:runId",
        element: <RunDetailLayout />,
        children: runDetailChildren,
      },

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
