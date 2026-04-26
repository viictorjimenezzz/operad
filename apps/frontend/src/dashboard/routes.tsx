import { BenchmarkDetailPage } from "@/dashboard/pages/BenchmarkDetailPage";
import { BenchmarksPage } from "@/dashboard/pages/BenchmarksPage";
import { Shell } from "@/dashboard/Shell";
import { NotFoundPage } from "@/dashboard/pages/NotFoundPage";
import { RunDetailPage } from "@/dashboard/pages/RunDetailPage";
import { RunListPage } from "@/dashboard/pages/RunListPage";
import { createBrowserRouter } from "react-router-dom";

export const dashboardRouter = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <RunListPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
      { path: "benchmarks", element: <BenchmarksPage /> },
      { path: "benchmarks/:benchmarkId", element: <BenchmarkDetailPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
