import { cn } from "@/lib/utils";
import {
  Activity,
  Beaker,
  Boxes,
  Database,
  GitBranch,
  GraduationCap,
  Layers,
  Workflow,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

/**
 * The 48px global rail along the left edge — the W&B project-level
 * navigation. Each entry switches the section sidebar.
 *
 * Routes are matched by prefix so e.g. /agents/abc123 still highlights
 * the Agents rail.
 */
export interface GlobalRailItem {
  id: string;
  to: string;
  /** Match all routes starting with one of these (or `to`). */
  prefixes?: string[];
  label: string;
  icon: ReactNode;
}

const RAIL_ITEMS: GlobalRailItem[] = [
  {
    id: "agents",
    to: "/agents",
    prefixes: ["/agents", "/runs"],
    label: "Agents",
    icon: <Layers size={16} />,
  },
  {
    id: "algorithms",
    to: "/algorithms",
    label: "Algorithms",
    icon: <Workflow size={16} />,
  },
  {
    id: "training",
    to: "/training",
    label: "Training",
    icon: <GraduationCap size={16} />,
  },
  {
    id: "opro",
    to: "/opro",
    label: "OPRO",
    icon: <Beaker size={16} />,
  },
  {
    id: "experiments",
    to: "/experiments",
    label: "Experiments",
    icon: <GitBranch size={16} />,
  },
  {
    id: "benchmarks",
    to: "/benchmarks",
    label: "Benchmarks",
    icon: <Activity size={16} />,
  },
  {
    id: "cassettes",
    to: "/cassettes",
    label: "Cassettes",
    icon: <Database size={16} />,
  },
  {
    id: "archive",
    to: "/archive",
    label: "Archive",
    icon: <Boxes size={16} />,
  },
];

export function GlobalRail() {
  const location = useLocation();
  return (
    <nav
      aria-label="dashboard sections"
      className="flex h-full w-12 flex-shrink-0 flex-col items-center gap-1 border-r border-border bg-bg-1 py-2"
    >
      {RAIL_ITEMS.map((it) => {
        const prefixes = it.prefixes ?? [it.to];
        const isActive =
          (it.to === "/" && location.pathname === "/") ||
          prefixes.some((p) => location.pathname === p || location.pathname.startsWith(`${p}/`));
        return (
          <NavLink
            key={it.id}
            to={it.to}
            aria-label={it.label}
            title={it.label}
            className={cn(
              "group relative flex h-9 w-9 items-center justify-center rounded-lg transition-colors duration-[var(--motion-quick)]",
              isActive ? "bg-bg-3 text-text" : "text-muted-2 hover:bg-bg-2 hover:text-text",
            )}
          >
            {it.icon}
            {isActive ? (
              <span
                aria-hidden
                className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-r-full bg-accent"
              />
            ) : null}
            <span
              className="pointer-events-none absolute left-[110%] top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-md border border-border-strong bg-bg-1 px-2 py-1 text-[11px] font-medium text-text opacity-0 shadow-[var(--shadow-popover)] transition-opacity group-hover:opacity-100"
              role="tooltip"
            >
              {it.label}
            </span>
          </NavLink>
        );
      })}
    </nav>
  );
}
