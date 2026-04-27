import { GlobalRail } from "@/components/panels/global-rail";
import { GlobalStatsBar } from "@/components/panels/global-stats-bar";
import { SectionSidebar } from "@/components/panels/section-sidebar/section-sidebar";
import { useDashboardStream } from "@/hooks/use-event-stream";
import { useUIStore } from "@/stores";
import { Outlet, useLocation } from "react-router-dom";

/**
 * Three-region shell:
 *   1. global rail (48px)         — section navigation
 *   2. section sidebar (280/56px) — group/run tree
 *   3. main canvas                — outlet
 *
 * Global rails that have their own page-level navigation (benchmarks,
 * cassettes, experiments, archive) hide the section sidebar.
 */
export function Shell() {
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const location = useLocation();

  useDashboardStream("/stream");

  const path = location.pathname;
  const showSectionSidebar =
    path === "/" ||
    path.startsWith("/agents") ||
    path.startsWith("/algorithms") ||
    path.startsWith("/training") ||
    path.startsWith("/runs");

  return (
    <div className="flex h-screen flex-col bg-bg">
      <GlobalStatsBar subtitle="dashboard" />
      <div className="flex flex-1 overflow-hidden">
        <GlobalRail />
        {showSectionSidebar ? (
          <div
            className="flex flex-shrink-0 overflow-hidden transition-[width] duration-200 ease-out"
            style={{ width: sidebarCollapsed ? 56 : 280 }}
          >
            <SectionSidebar />
          </div>
        ) : null}
        <main aria-label="dashboard main" className="flex flex-1 flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
