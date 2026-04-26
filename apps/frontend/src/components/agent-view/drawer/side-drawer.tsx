import { DrawerHost, getDrawerHeader } from "@/components/agent-view/drawer/drawer-host";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores";
import { clampDrawerWidth } from "@/stores/ui";
import { PanelRightClose, X } from "lucide-react";
import { type MouseEvent as ReactMouseEvent, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";

export function SideDrawer() {
  const drawer = useUIStore((s) => s.drawer);
  const drawerWidth = useUIStore((s) => s.drawerWidth);
  const closeDrawer = useUIStore((s) => s.closeDrawer);
  const setDrawerWidth = useUIStore((s) => s.setDrawerWidth);
  const setSidebarCollapsed = useUIStore((s) => s.setSidebarCollapsed);
  const { runId = "" } = useParams<{ runId: string }>();

  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);
  const isOpen = drawer !== null;

  useEffect(() => {
    if (!Number.isFinite(drawerWidth)) {
      setDrawerWidth(480);
      return;
    }
    const clamped = clampDrawerWidth(drawerWidth);
    if (clamped !== drawerWidth) setDrawerWidth(clamped);
  }, [drawerWidth, setDrawerWidth]);

  useEffect(() => {
    const onWindowResize = () => setDrawerWidth(drawerWidth);
    window.addEventListener("resize", onWindowResize);
    return () => window.removeEventListener("resize", onWindowResize);
  }, [drawerWidth, setDrawerWidth]);

  useEffect(() => {
    if (!isOpen) return;

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDrawer();
    };
    const onOutsidePointerDown = (event: MouseEvent) => {
      if (!panelRef.current) return;
      if (event.target instanceof Node && panelRef.current.contains(event.target)) return;
      closeDrawer();
    };

    window.addEventListener("keydown", onEscape);
    window.addEventListener("mousedown", onOutsidePointerDown);
    return () => {
      window.removeEventListener("keydown", onEscape);
      window.removeEventListener("mousedown", onOutsidePointerDown);
    };
  }, [isOpen, closeDrawer]);

  useEffect(() => {
    if (isOpen && !wasOpenRef.current) {
      previousFocusRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
      queueMicrotask(() => closeButtonRef.current?.focus());
    }

    if (!isOpen && wasOpenRef.current) {
      previousFocusRef.current?.focus();
      previousFocusRef.current = null;
    }

    wasOpenRef.current = isOpen;
  }, [isOpen]);

  const onResizeStart = (event: ReactMouseEvent<HTMLDivElement>) => {
    event.preventDefault();

    const onMove = (moveEvent: MouseEvent) => {
      setDrawerWidth(window.innerWidth - moveEvent.clientX);
    };
    const onUp = () => {
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const header = drawer ? getDrawerHeader(drawer, runId) : null;

  return (
    <aside
      ref={panelRef}
      aria-label="inspector drawer"
      className={cn(
        "fixed right-0 top-12 z-40 h-[calc(100vh-3rem)] border-l border-border bg-bg-1 shadow-[-10px_0_30px_rgba(0,0,0,0.22)] transition-transform duration-200 ease-out",
        isOpen ? "translate-x-0" : "translate-x-full",
      )}
      style={{ width: drawerWidth }}
    >
      <div
        role="separator"
        aria-label="Resize drawer"
        aria-orientation="vertical"
        className="absolute left-0 top-0 h-full w-1 -translate-x-1 cursor-col-resize"
        onMouseDown={onResizeStart}
      />
      <div className="flex h-full flex-col">
        <header className="flex items-start gap-2 border-b border-border px-3 py-2">
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold">{header?.title ?? ""}</div>
            {header?.subtitle ? (
              <div className="truncate font-mono text-[11px] text-muted">{header.subtitle}</div>
            ) : null}
          </div>
          <div className="flex items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              aria-label="Collapse runs sidebar"
              title="Collapse runs sidebar (cmd+\\)"
              onClick={() => setSidebarCollapsed(true)}
            >
              <PanelRightClose size={14} />
            </Button>
            <Button
              ref={closeButtonRef}
              size="icon"
              variant="ghost"
              aria-label="Close drawer"
              onClick={closeDrawer}
            >
              <X size={14} />
            </Button>
          </div>
        </header>
        <div className="min-h-0 flex-1">{isOpen ? <DrawerHost /> : null}</div>
      </div>
    </aside>
  );
}
