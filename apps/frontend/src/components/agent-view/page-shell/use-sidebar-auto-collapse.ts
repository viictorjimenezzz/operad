import { useUIStore } from "@/stores";
import { useEffect, useRef } from "react";

/**
 * Auto-collapses the runs sidebar while a route is mounted (e.g. while
 * the Graph tab is active) and restores the previous collapsed state on
 * unmount. Triggered explicitly per route via this hook.
 */
export function useSidebarAutoCollapse(active = true) {
  const setSidebarCollapsed = useUIStore((s) => s.setSidebarCollapsed);
  const previous = useRef<boolean | null>(null);

  useEffect(() => {
    if (!active) return;
    const wasCollapsed = useUIStore.getState().sidebarCollapsed;
    previous.current = wasCollapsed;
    if (!wasCollapsed) setSidebarCollapsed(true);
    return () => {
      if (previous.current === false) setSidebarCollapsed(false);
      previous.current = null;
    };
  }, [active, setSidebarCollapsed]);
}
