import { cn } from "@/lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

export const Toolbar = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex items-center gap-2 border-b border-border bg-bg-1 px-3 py-1.5 text-xs",
        className,
      )}
      {...rest}
    />
  ),
);
Toolbar.displayName = "Toolbar";
