import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export interface KeyValueGridProps {
  rows: Array<{ key: string; value: ReactNode; mono?: boolean }>;
  density?: "default" | "compact";
  align?: "default" | "right";
  className?: string;
}

export function KeyValueGrid({
  rows,
  density = "default",
  align = "default",
  className,
}: KeyValueGridProps) {
  const padY = density === "compact" ? "py-0.5" : "py-1";
  return (
    <div className={cn("grid grid-cols-[max-content_1fr] gap-x-3", className)}>
      {rows.map((row, i) => (
        <div key={i} className="contents">
          <div className={cn("text-[11px] uppercase tracking-[0.06em] text-muted", padY)}>
            {row.key}
          </div>
          <div
            className={cn(
              "min-w-0 truncate text-[13px] text-text",
              row.mono && "font-mono text-[12px]",
              align === "right" && "text-right",
              padY,
            )}
          >
            {row.value}
          </div>
        </div>
      ))}
    </div>
  );
}
