import { cn } from "@/lib/utils";
import * as RadixTabs from "@radix-ui/react-tabs";
import { type ComponentProps, forwardRef } from "react";

export const Tabs = RadixTabs.Root;

export const TabsList = forwardRef<HTMLDivElement, ComponentProps<typeof RadixTabs.List>>(
  ({ className, ...rest }, ref) => (
    <RadixTabs.List
      ref={ref}
      className={cn("flex gap-1 border-b border-border px-2", className)}
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
        "rounded-t-md border-x border-t border-transparent px-3 py-1.5 text-xs text-muted transition-colors hover:text-text",
        "data-[state=active]:border-border data-[state=active]:bg-bg-1 data-[state=active]:text-text",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent",
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
      className={cn("mt-2 focus-visible:outline-none data-[state=inactive]:hidden", className)}
      {...rest}
    />
  ),
);
TabsContent.displayName = "TabsContent";
