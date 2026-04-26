import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export interface DividerProps extends HTMLAttributes<HTMLHRElement> {
  orientation?: "horizontal" | "vertical";
}

export function Divider({ className, orientation = "horizontal", ...rest }: DividerProps) {
  return (
    <hr
      aria-orientation={orientation}
      className={cn(
        "border-0",
        orientation === "horizontal" ? "h-px w-full bg-border" : "h-full w-px bg-border",
        className,
      )}
      {...rest}
    />
  );
}
