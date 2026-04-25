import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export interface KPIProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  className?: string;
}

export function KPI({ label, value, sub, className }: KPIProps) {
  return (
    <div className={cn("flex flex-col gap-0.5 min-w-[70px]", className)}>
      <span className="text-[0.68rem] uppercase tracking-[0.08em] text-muted">{label}</span>
      <strong className="text-[1.02rem] font-semibold tabular-nums">{value}</strong>
      {sub != null && <span className="text-[0.7rem] text-muted-2">{sub}</span>}
    </div>
  );
}
