import { SideDrawer } from "@/components/agent-view/drawer/side-drawer";
import "@/components/agent-view/drawer/views/values";
import "@/components/agent-view/drawer/views/prompts";
import type { ComponentRegistry } from "@json-render/react";

import "@/components/agent-view/drawer/views/events";
import "@/components/agent-view/drawer/views/langfuse";
import "@/components/agent-view/drawer/views/diff";
import "@/components/agent-view/drawer/views/gradients";

export const drawerDefinitions = {} as const;
export const drawerComponents: ComponentRegistry = {
  SideDrawer: () => <SideDrawer />,
};
