import { cn } from "@/lib/utils";
import type { HTMLAttributes, ReactNode } from "react";

/**
 * Responsive panel grid for the workspace canvas. Lays out PanelCards
 * with W&B-style breathing room.
 *
 * `cols` controls the grid template at the lg breakpoint; below lg we
 * always collapse to a single column. `span` lets a child claim more
 * than one column.
 */
export interface PanelGridProps extends HTMLAttributes<HTMLDivElement> {
  cols?: 1 | 2 | 3 | 4;
  gap?: "sm" | "md" | "lg";
  children?: ReactNode;
}

const GAP: Record<NonNullable<PanelGridProps["gap"]>, string> = {
  sm: "gap-2",
  md: "gap-3",
  lg: "gap-4",
};

const COLS: Record<NonNullable<PanelGridProps["cols"]>, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 lg:grid-cols-2",
  3: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4",
};

export function PanelGrid({
  cols = 3,
  gap = "md",
  className,
  children,
  ...rest
}: PanelGridProps) {
  return (
    <div className={cn("grid", COLS[cols], GAP[gap], className)} {...rest}>
      {children}
    </div>
  );
}

/**
 * Wrapper that lets a child PanelCard span multiple columns/rows
 * without leaking grid props onto the panel itself.
 */
export interface PanelGridItemProps extends HTMLAttributes<HTMLDivElement> {
  colSpan?: 1 | 2 | 3 | 4;
  rowSpan?: 1 | 2;
}

const COL_SPAN: Record<NonNullable<PanelGridItemProps["colSpan"]>, string> = {
  1: "lg:col-span-1",
  2: "lg:col-span-2",
  3: "lg:col-span-3",
  4: "lg:col-span-4",
};

const ROW_SPAN: Record<NonNullable<PanelGridItemProps["rowSpan"]>, string> = {
  1: "lg:row-span-1",
  2: "lg:row-span-2",
};

export function PanelGridItem({
  colSpan = 1,
  rowSpan = 1,
  className,
  children,
  ...rest
}: PanelGridItemProps) {
  return (
    <div
      className={cn(COL_SPAN[colSpan], ROW_SPAN[rowSpan], "min-w-0", className)}
      {...rest}
    >
      {children}
    </div>
  );
}

/**
 * Visually labelled section (W&B's "System (23)" header above a grid).
 */
export interface PanelSectionProps extends HTMLAttributes<HTMLDivElement> {
  label: ReactNode;
  count?: number;
  toolbar?: ReactNode;
}

export function PanelSection({
  label,
  count,
  toolbar,
  className,
  children,
  ...rest
}: PanelSectionProps) {
  return (
    <section className={cn("flex flex-col gap-2", className)} {...rest}>
      <div className="flex items-center gap-2 px-1">
        <h3 className="m-0 text-[12px] font-medium uppercase tracking-[0.08em] text-muted">
          {label}
        </h3>
        {count != null ? (
          <span className="rounded-full bg-bg-3 px-1.5 py-px text-[10px] tabular-nums text-muted-2">
            {count}
          </span>
        ) : null}
        {toolbar != null ? <div className="ml-auto flex items-center gap-2">{toolbar}</div> : null}
      </div>
      {children}
    </section>
  );
}
