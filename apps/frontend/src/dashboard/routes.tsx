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
import { createBrowserRouter } from "react-router-dom";

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
          { path: "graph", element: <GraphTab /> },
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
