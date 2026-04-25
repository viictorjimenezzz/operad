import { useDashboardStream } from "@/hooks/use-event-stream";
import { GlobalStatsBar } from "@/shared/panels/global-stats-bar";
import { RunListSidebar } from "@/shared/panels/run-list-sidebar";
import { Outlet } from "react-router-dom";

export function Shell() {
  // Single multiplex /stream subscription for the whole dashboard.
  useDashboardStream("/stream");
  return (
    <div className="flex h-screen flex-col">
      <GlobalStatsBar subtitle="dashboard" />
      <div className="grid flex-1 grid-cols-[260px_1fr] overflow-hidden">
        <RunListSidebar />
        <main aria-label="run detail" className="flex h-full flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
