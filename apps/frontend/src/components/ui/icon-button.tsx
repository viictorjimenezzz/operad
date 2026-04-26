import { cn } from "@/lib/utils";
import { type ButtonHTMLAttributes, forwardRef } from "react";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  size?: "sm" | "md" | "lg";
  tone?: "default" | "accent" | "danger";
}

const SIZE: Record<NonNullable<IconButtonProps["size"]>, string> = {
  sm: "h-7 w-7",
  md: "h-8 w-8",
  lg: "h-9 w-9",
};

const TONE: Record<NonNullable<IconButtonProps["tone"]>, string> = {
  default: "text-muted hover:text-text hover:bg-bg-3",
  accent: "text-accent hover:bg-[--color-accent-dim]",
  danger: "text-[--color-err] hover:bg-[--color-err-dim]",
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    { size = "md", tone = "default", active, className, children, type = "button", ...rest },
    ref,
  ) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex flex-shrink-0 items-center justify-center rounded-lg border transition-colors duration-[var(--motion-quick)] ease-out",
        SIZE[size],
        active ? "border-border-strong bg-bg-3 text-text" : "border-transparent",
        TONE[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  ),
);
IconButton.displayName = "IconButton";
