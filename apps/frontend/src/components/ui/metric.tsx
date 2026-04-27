import { cn } from "@/lib/utils";
import type { HTMLAttributes, ReactNode } from "react";

export interface MetricProps extends HTMLAttributes<HTMLSpanElement> {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "default" | "muted";
}

export function Metric({ label, value, sub, tone = "default", className, ...rest }: MetricProps) {
  return (
    <span
      className={cn("inline-flex items-baseline gap-1.5 leading-none", className)}
      {...rest}
    >
      <span className="text-[10px] font-medium uppercase tracking-[0.06em] text-muted-2">
        {label}
      </span>
      <span
        className={cn(
          "text-[12px] tabular-nums",
          tone === "muted" ? "text-muted" : "text-text",
        )}
      >
        {value}
      </span>
      {sub != null ? <span className="font-mono text-[10px] text-muted-2">{sub}</span> : null}
    </span>
  );
}
