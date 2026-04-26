import { CassetteDetailPage } from "@/dashboard/pages/CassetteDetailPage";
import { CassettesPage } from "@/dashboard/pages/CassettesPage";
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
      { path: "cassettes", element: <CassettesPage /> },
      { path: "cassettes/*", element: <CassetteDetailPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const dashboardRouter = createBrowserRouter(dashboardRoutes);
