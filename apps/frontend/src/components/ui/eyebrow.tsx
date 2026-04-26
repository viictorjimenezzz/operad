import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export interface EyebrowProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "default" | "muted" | "accent";
}

const TONE: Record<NonNullable<EyebrowProps["tone"]>, string> = {
  default: "text-text",
  muted: "text-muted",
  accent: "text-accent",
};

export function Eyebrow({ tone = "muted", className, children, ...rest }: EyebrowProps) {
  return (
    <span
      className={cn("text-[11px] font-medium uppercase tracking-[0.08em]", TONE[tone], className)}
      {...rest}
    >
      {children}
    </span>
  );
}
