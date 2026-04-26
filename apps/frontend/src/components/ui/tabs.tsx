import { cn } from "@/lib/utils";
import * as RadixTabs from "@radix-ui/react-tabs";
import { type ComponentProps, forwardRef } from "react";

export const Tabs = RadixTabs.Root;

export const TabsList = forwardRef<HTMLDivElement, ComponentProps<typeof RadixTabs.List>>(
  ({ className, ...rest }, ref) => (
    <RadixTabs.List
      ref={ref}
      className={cn("flex items-center gap-2 border-b border-border", className)}
      {...rest}
    />
  ),
);
TabsList.displayName = "TabsList";

export const TabsTrigger = forwardRef<HTMLButtonElement, ComponentProps<typeof RadixTabs.Trigger>>(
  ({ className, ...rest }, ref) => (
    <RadixTabs.Trigger
      ref={ref}
      className={cn(
        "relative h-9 px-3 text-[13px] font-medium text-muted transition-colors duration-[var(--motion-quick)] hover:text-text",
        "data-[state=active]:text-text",
        "after:absolute after:inset-x-3 after:bottom-0 after:h-[2px] after:rounded-t-full after:bg-transparent after:transition-colors after:duration-[var(--motion-tab)]",
        "data-[state=active]:after:bg-accent",
        "focus-visible:outline-none focus-visible:after:bg-accent",
        className,
      )}
      {...rest}
    />
  ),
);
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = forwardRef<HTMLDivElement, ComponentProps<typeof RadixTabs.Content>>(
  ({ className, ...rest }, ref) => (
    <RadixTabs.Content
      ref={ref}
      className={cn("focus-visible:outline-none data-[state=inactive]:hidden", className)}
      {...rest}
    />
  ),
);
TabsContent.displayName = "TabsContent";
