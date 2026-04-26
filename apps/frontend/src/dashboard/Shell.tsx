import { GlobalStatsBar } from "@/components/panels/global-stats-bar";
import { RunListSidebar } from "@/components/panels/runs-sidebar/run-list-sidebar";
import { useDashboardStream } from "@/hooks/use-event-stream";
import { useUIStore } from "@/stores";
import { Outlet } from "react-router-dom";

export function Shell() {
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const drawer = useUIStore((s) => s.drawer);
  const drawerWidth = useUIStore((s) => s.drawerWidth);

  // Single multiplex /stream subscription for the whole dashboard.
  useDashboardStream("/stream");
  return (
    <div className="flex h-screen flex-col">
      <GlobalStatsBar subtitle="dashboard" />
      <div
        className="grid flex-1 overflow-hidden transition-[grid-template-columns] duration-200 ease-out"
        style={{
          gridTemplateColumns: `${sidebarCollapsed ? 56 : 300}px 1fr ${drawer ? drawerWidth : 0}px`,
        }}
      >
        <RunListSidebar />
        <main aria-label="run detail" className="flex h-full flex-col overflow-hidden">
          <Outlet />
        </main>
        <aside
          aria-label="inspector drawer"
          className="overflow-hidden border-l border-border bg-bg-1 transition-opacity duration-200 ease-out"
          style={{ opacity: drawer ? 1 : 0 }}
        />
      </div>
    </div>
  );
}
