import { cn } from "@/lib/utils";
import { type VariantProps, cva } from "class-variance-authority";
import { type HTMLAttributes, forwardRef } from "react";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[0.7rem] font-medium uppercase tracking-[0.05em]",
  {
    variants: {
      variant: {
        default: "border-border bg-bg-3 text-muted",
        live: "border-ok bg-ok-dim text-[#aaf0be]",
        ended: "border-border bg-bg-3 text-muted",
        error: "border-err bg-err-dim text-[#ffc0c8]",
        algo: "border-[--color-algo] bg-bg-3 text-[--color-algo]",
        warn: "border-warn bg-bg-3 text-warn",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...rest }, ref) => (
    <span ref={ref} className={cn(badgeVariants({ variant }), className)} {...rest} />
  ),
);
Badge.displayName = "Badge";
