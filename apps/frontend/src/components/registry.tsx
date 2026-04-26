import { agentViewRegistry } from "@/components/agent-view/registry";
import { algorithmsRegistry } from "@/components/algorithms/registry";
import { chartsRegistry } from "@/components/charts/registry";
import { panelsRegistry } from "@/components/panels/registry";
import { uiRegistry } from "@/components/ui/registry";
import type { ComponentRegistry } from "@json-render/react";

export const registry: ComponentRegistry = {
  ...uiRegistry,
  ...panelsRegistry,
  ...chartsRegistry,
  ...algorithmsRegistry,
  ...agentViewRegistry,
};
