import { BenchmarkDetailPage } from "@/dashboard/pages/BenchmarkDetailPage";
import { BenchmarksPage } from "@/dashboard/pages/BenchmarksPage";
import { CassetteDetailPage } from "@/dashboard/pages/CassetteDetailPage";
import { CassettesPage } from "@/dashboard/pages/CassettesPage";
import { ExperimentsPage } from "@/dashboard/pages/ExperimentsPage";
import { Shell } from "@/dashboard/Shell";
import { NotFoundPage } from "@/dashboard/pages/NotFoundPage";
import { RunDetailPage } from "@/dashboard/pages/RunDetailPage";
import { RunListPage } from "@/dashboard/pages/RunListPage";
import { createBrowserRouter } from "react-router-dom";

export const dashboardRoutes = [
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <RunListPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
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
