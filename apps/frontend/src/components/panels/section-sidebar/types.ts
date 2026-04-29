export type SidebarRail = "agents" | "algorithms" | "training" | "opro";

export type SidebarFilters = {
  timeRange: "all" | "1h" | "24h";
  state: "all" | "running" | "ended" | "error";
  className: string;
  invocationCount: "all" | "single" | "multi";
  backend: string;
  model: string;
  script: string;
  algorithm: string;
  trainee: string;
};

export const DEFAULT_SIDEBAR_FILTERS: SidebarFilters = {
  timeRange: "all",
  state: "all",
  className: "all",
  invocationCount: "all",
  backend: "all",
  model: "all",
  script: "all",
  algorithm: "all",
  trainee: "all",
};

