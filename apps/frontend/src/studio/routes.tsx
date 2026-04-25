import { NotFoundPage } from "@/dashboard/pages/NotFoundPage";
import { StudioShell } from "@/studio/Shell";
import { JobDetailPage } from "@/studio/pages/JobDetailPage";
import { JobsIndexPage } from "@/studio/pages/JobsIndexPage";
import { createBrowserRouter } from "react-router-dom";

export const studioRouter = createBrowserRouter([
  {
    path: "/",
    element: <StudioShell />,
    children: [
      { index: true, element: <JobsIndexPage /> },
      { path: "jobs/:jobName", element: <JobDetailPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
