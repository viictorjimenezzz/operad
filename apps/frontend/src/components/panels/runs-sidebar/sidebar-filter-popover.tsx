import { IconButton } from "@/components/ui";
import { cn } from "@/lib/utils";
import { type RunStatusFilter, type RunTimeFilter, useRunsFilterStore } from "@/stores/runs-filter";
import { Filter } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const TIME_OPTIONS: Array<{ value: RunTimeFilter; label: string }> = [
  { value: "all", label: "All time" },
  { value: "1h", label: "Last hour" },
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
];

const STATUS_OPTIONS: Array<{ value: RunStatusFilter; label: string }> = [
  { value: "all", label: "Any" },
  { value: "running", label: "Running" },
  { value: "ended", label: "Ended" },
  { value: "errors", label: "Errors" },
];

export function SidebarFilterPopover() {
  const {
    statusFilter,
    timeFilter,
    showSynthetic,
    setStatusFilter,
    setTimeFilter,
    setShowSynthetic,
  } = useRunsFilterStore();
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  const active = statusFilter !== "all" || timeFilter !== "all" || showSynthetic;

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!popoverRef.current) return;
      if (e.target instanceof Node && popoverRef.current.contains(e.target)) return;
      setOpen(false);
    };
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  return (
    <div className="relative">
      <IconButton
        aria-label="filter runs"
        onClick={() => setOpen((v) => !v)}
        active={open || active}
        size="sm"
        title="filters"
      >
        <Filter size={13} />
        {active ? (
          <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-accent" />
        ) : null}
      </IconButton>
      {open ? (
        <section
          ref={popoverRef}
          aria-label="run filters"
          className="absolute right-0 top-full z-30 mt-1 w-[260px] rounded-xl border border-border-strong bg-bg-1 p-3 shadow-[var(--shadow-popover)]"
        >
          <div className="mb-3">
            <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
              Time
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {TIME_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setTimeFilter(o.value)}
                  className={cn(
                    "rounded-md border px-2 py-1.5 text-[12px] transition-colors",
                    timeFilter === o.value
                      ? "border-border-strong bg-bg-3 text-text"
                      : "border-transparent text-muted hover:bg-bg-3 hover:text-text",
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
          <div className="mb-3">
            <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-muted">
              Status
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {STATUS_OPTIONS.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setStatusFilter(o.value)}
                  className={cn(
                    "rounded-md border px-2 py-1.5 text-[12px] transition-colors",
                    statusFilter === o.value
                      ? "border-border-strong bg-bg-3 text-text"
                      : "border-transparent text-muted hover:bg-bg-3 hover:text-text",
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
          <label className="flex cursor-pointer items-center gap-2 rounded-md p-1 text-[12px] text-text hover:bg-bg-3">
            <input
              type="checkbox"
              checked={showSynthetic}
              onChange={(e) => setShowSynthetic(e.target.checked)}
              className="h-3.5 w-3.5 cursor-pointer accent-[--color-accent]"
            />
            Show inner runs (children of algorithms)
          </label>
        </section>
      ) : null}
    </div>
  );
}
