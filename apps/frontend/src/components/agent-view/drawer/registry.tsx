import { SideDrawer } from "@/components/agent-view/drawer/side-drawer";
import "@/components/agent-view/drawer/views/values";
import type { ComponentRegistry } from "@json-render/react";

export const drawerDefinitions = {} as const;
export const drawerComponents: ComponentRegistry = {
  SideDrawer: () => <SideDrawer />,
};
