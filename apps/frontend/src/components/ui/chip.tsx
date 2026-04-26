import { cn } from "@/lib/utils";
import { type ButtonHTMLAttributes, forwardRef } from "react";

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export const Chip = forwardRef<HTMLButtonElement, ChipProps>(
  ({ className, active = false, type = "button", ...rest }, ref) => (
    <button
      ref={ref}
      type={type}
      data-state={active ? "active" : "inactive"}
      className={cn(
        "rounded-full border px-2.5 py-0.5 text-[0.72rem] tracking-[0.03em] transition-colors",
        active
          ? "border-accent bg-accent-dim text-text"
          : "border-border bg-bg-2 text-muted hover:border-border-strong hover:text-text",
        className,
      )}
      {...rest}
    />
  ),
);
Chip.displayName = "Chip";
