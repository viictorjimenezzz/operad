import { AgentsTree } from "@/components/panels/section-sidebar/agents-tree";
import { AlgorithmsTree } from "@/components/panels/section-sidebar/algorithms-tree";
import { OPROTree } from "@/components/panels/section-sidebar/opro-tree";
import { TrainingTree } from "@/components/panels/section-sidebar/training-tree";
import { IconButton } from "@/components/ui";
import { useUIStore } from "@/stores";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

/**
 * Adaptive section sidebar — what's rendered depends on the active rail
 * (agents / algorithms / training). All three render the same
 * three-level GroupTree with the same filter/sort strip on top.
 */
export function SectionSidebar() {
  const location = useLocation();
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const toggleButtonRef = useRef<HTMLButtonElement>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key !== "\\") return;
      event.preventDefault();
      toggleSidebar();
      queueMicrotask(() => toggleButtonRef.current?.focus());
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggleSidebar]);

  const onSearchChange = (e: ChangeEvent<HTMLInputElement>) => setSearch(e.target.value);

  const path = location.pathname;
  const rail = path.startsWith("/algorithms")
    ? "algorithms"
    : path.startsWith("/training")
      ? "training"
      : path.startsWith("/opro")
        ? "opro"
        : "agents";

  const railTitle =
    rail === "algorithms"
      ? "Algorithms"
      : rail === "training"
        ? "Training"
        : rail === "opro"
          ? "OPRO"
          : "Agents";
  const showTitleBar = rail !== "agents" || sidebarCollapsed;

  return (
    <aside
      className="relative flex h-full flex-col border-r border-border bg-bg-1"
      style={{ transition: "width 200ms ease" }}
    >
      {showTitleBar ? (
        <div className="flex items-center gap-1.5 border-b border-border px-2 py-2">
          {!sidebarCollapsed ? (
            <>
              <span className="px-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-text">
                {railTitle}
              </span>
              <span className="ml-auto" />
            </>
          ) : (
            <span className="ml-auto" />
          )}
          <IconButton
            ref={toggleButtonRef}
            aria-label={sidebarCollapsed ? "expand sidebar" : "collapse sidebar"}
            aria-expanded={!sidebarCollapsed}
            onClick={toggleSidebar}
            title="toggle (cmd+\\)"
            size="sm"
          >
            {sidebarCollapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </IconButton>
        </div>
      ) : null}

      {!sidebarCollapsed ? (
        <>
          <div className="flex items-center gap-2 border-b border-border bg-bg-1/60 px-2 py-1.5">
            <div className="relative flex h-7 w-full items-center rounded-md border border-border bg-bg px-2 focus-within:border-border-strong">
              <Search size={12} className="text-muted-2" />
              <input
                type="text"
                value={search}
                onChange={onSearchChange}
                placeholder="Search…"
                className="ml-1.5 w-full bg-transparent text-[12px] text-text outline-none placeholder:text-muted-2"
              />
            </div>
            {!showTitleBar ? (
              <IconButton
                ref={toggleButtonRef}
                aria-label="collapse sidebar"
                aria-expanded
                onClick={toggleSidebar}
                title="toggle (cmd+\\)"
                size="sm"
              >
                <ChevronLeft size={13} />
              </IconButton>
            ) : null}
          </div>
          <div className="flex-1 overflow-auto">
            {rail === "agents" ? <AgentsTree search={search} /> : null}
            {rail === "algorithms" ? <AlgorithmsTree search={search} /> : null}
            {rail === "training" ? <TrainingTree search={search} /> : null}
            {rail === "opro" ? <OPROTree search={search} /> : null}
          </div>
        </>
      ) : (
        <div className="flex-1 overflow-auto px-1.5 py-2" />
      )}
    </aside>
  );
}
