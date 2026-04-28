import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function CompareSection({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section data-compare-section={title} className={cn("border border-border bg-bg-1", className)}>
      <div className="border-b border-border px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
        {title}
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}
