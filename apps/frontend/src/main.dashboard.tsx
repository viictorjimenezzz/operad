import { Providers } from "@/app/Providers";
import { App as DashboardApp } from "@/dashboard/App";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";

const container = document.getElementById("root");
if (!container) throw new Error("operad-dashboard: #root not found in document");

createRoot(container).render(
  <StrictMode>
    <Providers mode="dashboard">
      <DashboardApp />
    </Providers>
  </StrictMode>,
);
