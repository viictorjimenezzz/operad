import { dashboardRouter } from "@/dashboard/routes";
import { RouterProvider } from "react-router-dom";

export function App() {
  return <RouterProvider router={dashboardRouter} />;
}
