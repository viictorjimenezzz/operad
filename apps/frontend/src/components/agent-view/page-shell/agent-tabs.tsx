import { cn } from "@/lib/utils";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

export interface AgentTabsProps {
  base: string;
  tabs: Array<{ to: string; label: string; end?: boolean; badge?: ReactNode }>;
  className?: string;
  right?: ReactNode;
}

export function AgentTabs({ base, tabs, className, right }: AgentTabsProps) {
  return (
    <div
      className={cn(
        "sticky top-0 z-10 flex items-center gap-1 border-b border-border bg-bg-1/95 px-4 backdrop-blur-md",
        className,
      )}
    >
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={`${base}${t.to}`}
          end={t.end ?? t.to === ""}
          className={({ isActive }) =>
            cn(
              "relative flex h-11 items-center gap-2 px-3 text-[13px] font-medium transition-colors duration-[var(--motion-quick)]",
              "after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:rounded-t-full after:transition-colors after:duration-[var(--motion-tab)]",
              isActive
                ? "text-text after:bg-accent"
                : "text-muted hover:text-text after:bg-transparent",
            )
          }
        >
          {t.label}
          {t.badge ? (
            <span className="rounded-full bg-bg-3 px-1.5 py-px text-[10px] tabular-nums text-muted">
              {t.badge}
            </span>
          ) : null}
        </NavLink>
      ))}
      {right ? <div className="ml-auto flex items-center gap-2">{right}</div> : null}
    </div>
  );
}
