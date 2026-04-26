import type { ComponentRegistry } from "@json-render/react";
import { SideDrawer } from "@/components/agent-view/drawer/side-drawer";

export const drawerDefinitions = {} as const;
export const drawerComponents: ComponentRegistry = {
  SideDrawer: () => <SideDrawer />,
};
