import { ArchivePage } from "@/dashboard/pages/ArchivePage";
import { ArchivedRunPage } from "@/dashboard/pages/ArchivedRunPage";
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
      { path: "archive", element: <ArchivePage /> },
      { path: "archive/:runId", element: <ArchivedRunPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
