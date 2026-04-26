import { cn } from "@/lib/utils";
import type { HTMLAttributes, ReactNode } from "react";

export interface StatTileProps extends HTMLAttributes<HTMLDivElement> {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  size?: "sm" | "md" | "lg";
  align?: "left" | "right";
}

const SIZE: Record<NonNullable<StatTileProps["size"]>, { value: string; gap: string }> = {
  sm: { value: "text-sm font-medium", gap: "gap-0.5" },
  md: { value: "text-base font-medium", gap: "gap-1" },
  lg: { value: "text-xl font-medium", gap: "gap-1.5" },
};

export function StatTile({
  label,
  value,
  sub,
  size = "md",
  align = "left",
  className,
  ...rest
}: StatTileProps) {
  const cfg = SIZE[size];
  return (
    <div
      className={cn("flex flex-col", cfg.gap, align === "right" && "items-end", className)}
      {...rest}
    >
      <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
        {label}
      </span>
      <span className={cn(cfg.value, "tabular-nums text-text")}>{value}</span>
      {sub != null ? <span className="text-[11px] text-muted-2">{sub}</span> : null}
    </div>
  );
}
