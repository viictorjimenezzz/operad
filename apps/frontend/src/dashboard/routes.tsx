import { Shell } from "@/dashboard/Shell";
import { NotFoundPage } from "@/dashboard/pages/NotFoundPage";
import { RunDetailPage } from "@/dashboard/pages/RunDetailPage";
import { ExperimentsPage } from "@/dashboard/pages/ExperimentsPage";
import { RunListPage } from "@/dashboard/pages/RunListPage";
import { createBrowserRouter } from "react-router-dom";

export const dashboardRouter = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <RunListPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
      { path: "experiments", element: <ExperimentsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
