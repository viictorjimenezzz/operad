import { Providers } from "@/app/Providers";
import { App as StudioApp } from "@/studio/App";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@/styles/tokens.css";

const container = document.getElementById("root");
if (!container) throw new Error("operad-studio: #root not found in document");

createRoot(container).render(
  <StrictMode>
    <Providers mode="studio">
      <StudioApp />
    </Providers>
  </StrictMode>,
);
