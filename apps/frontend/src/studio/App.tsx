import { studioRouter } from "@/studio/routes";
import { RouterProvider } from "react-router-dom";

export function App() {
  return <RouterProvider router={studioRouter} />;
}
