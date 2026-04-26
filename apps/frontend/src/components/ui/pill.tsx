import { cn } from "@/lib/utils";
import type { HTMLAttributes, ReactNode } from "react";

export type PillTone = "default" | "live" | "ok" | "warn" | "error" | "accent" | "algo";

export interface PillProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: PillTone;
  size?: "sm" | "md";
  pulse?: boolean;
  icon?: ReactNode;
}

const TONE: Record<PillTone, string> = {
  default: "bg-bg-3 text-text",
  live: "bg-[--color-ok-dim] text-[--color-ok]",
  ok: "bg-[--color-ok-dim] text-[--color-ok]",
  warn: "bg-[--color-warn-dim] text-[--color-warn]",
  error: "bg-[--color-err-dim] text-[--color-err]",
  accent: "bg-[--color-accent-dim] text-[--color-accent-strong]",
  algo: "bg-[--color-algo-dim] text-[--color-algo]",
};

const SIZE: Record<NonNullable<PillProps["size"]>, string> = {
  sm: "h-5 px-2 text-[10px]",
  md: "h-6 px-2.5 text-[11px]",
};

export function Pill({
  tone = "default",
  size = "md",
  pulse,
  icon,
  className,
  children,
  ...rest
}: PillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium uppercase tracking-[0.06em]",
        TONE[tone],
        SIZE[size],
        className,
      )}
      {...rest}
    >
      {pulse ? (
        <span className="relative inline-flex h-1.5 w-1.5 flex-shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      ) : icon ? (
        <span className="flex-shrink-0">{icon}</span>
      ) : null}
      {children}
    </span>
  );
}
