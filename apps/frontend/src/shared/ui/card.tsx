import { cn } from "@/lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-md border border-border bg-bg-1 shadow-[inset_0_0_0_1px_rgba(0,0,0,0.2)]",
        className,
      )}
      {...rest}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex items-center justify-between gap-2 border-b border-border px-3 py-2",
        className,
      )}
      {...rest}
    />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...rest }, ref) => (
    <h3
      ref={ref}
      className={cn(
        "m-0 text-[0.72rem] font-medium uppercase tracking-[0.1em] text-muted",
        className,
      )}
      {...rest}
    />
  ),
);
CardTitle.displayName = "CardTitle";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...rest }, ref) => <div ref={ref} className={cn("p-3", className)} {...rest} />,
);
CardContent.displayName = "CardContent";
