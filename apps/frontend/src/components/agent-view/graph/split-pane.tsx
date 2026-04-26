import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores";
import { AnimatePresence, motion } from "framer-motion";
import {
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";

export interface SplitPaneProps {
  open: boolean;
  left: ReactNode;
  right: ReactNode;
}

const DRAG_SOURCE_ATTR = "data-split-resizing";

/**
 * Two-pane layout: left fills the rest, right slides in at a persisted
 * fraction of the viewport when `open` is true. Drag handle resizes.
 */
export function SplitPane({ open, left, right }: SplitPaneProps) {
  const fraction = useUIStore((s) => s.graphSplitFraction);
  const setFraction = useUIStore((s) => s.setGraphSplitFraction);
  const [dragging, setDragging] = useState(false);

  const onMouseDown = useCallback((event: ReactMouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(true);
    document.body.setAttribute(DRAG_SOURCE_ATTR, "true");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => {
      const total = window.innerWidth;
      const x = e.clientX;
      // The right pane's width = total - x; fraction = right / total.
      const f = Math.max(0.2, Math.min(0.8, (total - x) / total));
      setFraction(f);
    };
    const onUp = () => {
      setDragging(false);
      document.body.removeAttribute(DRAG_SOURCE_ATTR);
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging, setFraction]);

  const rightPct = open ? Math.round(fraction * 100) : 0;
  const leftPct = 100 - rightPct;

  return (
    <div className="relative flex h-full w-full overflow-hidden">
      <div
        className="relative h-full min-w-0"
        style={{
          width: `${leftPct}%`,
          transition: dragging ? "none" : "width 220ms cubic-bezier(.2,.8,.2,1)",
        }}
      >
        {left}
      </div>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="right"
            className="relative h-full min-w-0 border-l border-border-strong bg-bg-1"
            initial={{ width: "0%", opacity: 0 }}
            animate={{ width: `${rightPct}%`, opacity: 1 }}
            exit={{ width: "0%", opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <div
              role="separator"
              aria-label="resize inspector"
              aria-orientation="vertical"
              tabIndex={0}
              onMouseDown={onMouseDown}
              className={cn(
                "absolute -left-1 top-0 z-10 h-full w-2 cursor-col-resize",
                "before:absolute before:left-1 before:top-0 before:h-full before:w-px before:bg-border-strong",
                dragging && "before:bg-accent",
                "hover:before:bg-accent",
              )}
            />
            <div className="h-full overflow-hidden">{right}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
