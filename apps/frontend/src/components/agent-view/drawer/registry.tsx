import { SideDrawer } from "@/components/agent-view/drawer/side-drawer";
import type { ComponentRegistry } from "@json-render/react";

import "@/components/agent-view/drawer/views/events";
import "@/components/agent-view/drawer/views/langfuse";

export const drawerDefinitions = {} as const;
export const drawerComponents: ComponentRegistry = {
  SideDrawer: () => <SideDrawer />,
};
