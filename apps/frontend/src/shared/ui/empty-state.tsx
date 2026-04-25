import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  cta?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, cta, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex h-full flex-col items-center justify-center gap-2 p-6 text-center",
        className,
      )}
    >
      <h3 className="m-0 text-sm font-medium text-text">{title}</h3>
      {description != null && <p className="m-0 max-w-md text-xs text-muted">{description}</p>}
      {cta != null && <div className="mt-2">{cta}</div>}
    </div>
  );
}
