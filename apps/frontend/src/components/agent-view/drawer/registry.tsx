import { SideDrawer } from "@/components/agent-view/drawer/side-drawer";
import type { ComponentRegistry } from "@json-render/react";

export const drawerDefinitions = {} as const;

export const drawerComponents: ComponentRegistry = {
  SideDrawer: ({ element }) => {
    const p = element.props as { runId: string };
    return <SideDrawer runId={p.runId} />;
  },
};
