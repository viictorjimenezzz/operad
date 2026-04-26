import { DrawerHost, drawerTitle } from "@/components/agent-view/drawer/drawer-host";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores";
import { X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

interface SideDrawerProps {
  runId: string;
}

export function SideDrawer({ runId }: SideDrawerProps) {
  const drawer = useUIStore((s) => s.drawer);
  const closeDrawer = useUIStore((s) => s.closeDrawer);
  const drawerWidth = useUIStore((s) => s.drawerWidth);
  const setDrawerWidth = useUIStore((s) => s.setDrawerWidth);

  const open = Boolean(drawer);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeDrawer();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeDrawer]);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => {
      const width = window.innerWidth - e.clientX;
      setDrawerWidth(width);
    };
    const onUp = () => setDragging(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging, setDrawerWidth]);

  const title = useMemo(() => drawerTitle(drawer?.kind ?? null, drawer?.payload ?? {}), [drawer]);

  return (
    <aside
      className={cn(
        "fixed right-0 top-0 z-30 h-full border-l border-border bg-bg-1 shadow-[-8px_0_24px_rgba(0,0,0,0.35)] transition-transform duration-200",
        open ? "translate-x-0" : "translate-x-full",
      )}
      style={{ width: drawerWidth }}
      aria-hidden={!open}
    >
      <button
        type="button"
        className="absolute left-0 top-0 h-full w-1 -translate-x-full cursor-col-resize bg-transparent"
        onMouseDown={() => setDragging(true)}
        aria-label="resize drawer"
      />
      <div className="flex h-10 items-center justify-between border-b border-border px-2">
        <div className="truncate text-xs text-text">{title}</div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={closeDrawer}
          aria-label="close drawer"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="h-[calc(100%-2.5rem)] overflow-auto">
        {drawer ? <DrawerHost runId={runId} kind={drawer.kind} payload={drawer.payload} /> : null}
      </div>
    </aside>
  );
}
