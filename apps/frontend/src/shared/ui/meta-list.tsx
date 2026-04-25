import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export interface MetaItem {
  label: string;
  value: ReactNode;
}

export function MetaList({ items, className }: { items: MetaItem[]; className?: string }) {
  return (
    <dl className={cn("grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs", className)}>
      {items.map((it) => (
        <div key={it.label} className="contents">
          <dt className="text-muted">{it.label}</dt>
          <dd className="m-0 truncate text-text">{it.value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
