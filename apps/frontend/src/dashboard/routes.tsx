import { Shell } from "@/dashboard/Shell";
import { BenchmarkDetailPage } from "@/dashboard/pages/BenchmarkDetailPage";
import { BenchmarksPage } from "@/dashboard/pages/BenchmarksPage";
import { CassetteDetailPage } from "@/dashboard/pages/CassetteDetailPage";
import { CassettesPage } from "@/dashboard/pages/CassettesPage";
import { ExperimentsPage } from "@/dashboard/pages/ExperimentsPage";
import { NotFoundPage } from "@/dashboard/pages/NotFoundPage";
import { RunListPage } from "@/dashboard/pages/RunListPage";
import { CostTab } from "@/dashboard/pages/run-detail/CostTab";
import { DriftTab } from "@/dashboard/pages/run-detail/DriftTab";
import { GraphTab } from "@/dashboard/pages/run-detail/GraphTab";
import { InvocationsTab } from "@/dashboard/pages/run-detail/InvocationsTab";
import { OverviewTab } from "@/dashboard/pages/run-detail/OverviewTab";
import { RunDetailLayout } from "@/dashboard/pages/run-detail/RunDetailLayout";
import { TrainTab } from "@/dashboard/pages/run-detail/TrainTab";
import { createBrowserRouter, useRouteError } from "react-router-dom";

export const dashboardRoutes = [
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <RunListPage /> },
      {
        path: "runs/:runId",
        element: <RunDetailLayout />,
        children: [
          { index: true, element: <OverviewTab /> },
          { path: "graph", element: <GraphTab />, errorElement: <GraphRouteErrorBoundary /> },
          { path: "invocations", element: <InvocationsTab /> },
          { path: "train", element: <TrainTab /> },
          { path: "cost", element: <CostTab /> },
          { path: "drift", element: <DriftTab /> },
        ],
      },
      { path: "benchmarks", element: <BenchmarksPage /> },
      { path: "benchmarks/:benchmarkId", element: <BenchmarkDetailPage /> },
      { path: "cassettes", element: <CassettesPage /> },
      { path: "cassettes/*", element: <CassetteDetailPage /> },
      { path: "experiments", element: <ExperimentsPage /> },
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
