import { graphComponents } from "@/components/agent-view/graph/registry";
import { overviewRegistry } from "@/components/agent-view/overview/registry";
import type { ComponentRegistry } from "@json-render/react";

export const agentViewRegistry: ComponentRegistry = {
  ...graphComponents,
  ...overviewRegistry,
};
