import { cn } from "@/lib/utils";
import { type HTMLAttributes, forwardRef } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Visual elevation. */
  variant?: "raised" | "flat" | "inset";
  /** Disable internal padding (when content owns its own padding). */
  flush?: boolean;
}

const VARIANT: Record<NonNullable<CardProps["variant"]>, string> = {
  raised: "border border-border bg-bg-1 shadow-[var(--shadow-card-soft)]",
  flat: "border border-border bg-bg-1",
  inset: "border border-border bg-bg-inset",
};

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ variant = "raised", flush, className, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-xl", VARIANT[variant], !flush && "", className)}
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
        "flex items-center justify-between gap-3 border-b border-border px-4 py-3",
        className,
      )}
      {...rest}
    />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...rest }, ref) => (
    <h3 ref={ref} className={cn("m-0 text-sm font-medium text-text", className)} {...rest} />
  ),
);
CardTitle.displayName = "CardTitle";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...rest }, ref) => <div ref={ref} className={cn("p-4", className)} {...rest} />,
);
CardContent.displayName = "CardContent";
