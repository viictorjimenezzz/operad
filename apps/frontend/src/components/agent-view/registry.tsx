import { drawerComponents, drawerDefinitions } from "@/components/agent-view/drawer/registry";
import { graphComponents, graphDefinitions } from "@/components/agent-view/graph/registry";
import { insightsComponents, insightsDefinitions } from "@/components/agent-view/insights/registry";
import { metadataComponents, metadataDefinitions } from "@/components/agent-view/metadata/registry";
import type { ComponentRegistry } from "@json-render/react";

export const agentViewDefinitions = {
  ...metadataDefinitions,
  ...graphDefinitions,
  ...drawerDefinitions,
  ...insightsDefinitions,
} as const;

export const agentViewRegistry: ComponentRegistry = {
  ...metadataComponents,
  ...graphComponents,
  ...drawerComponents,
  ...insightsComponents,
};
