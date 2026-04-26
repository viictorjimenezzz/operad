import { cn } from "@/lib/utils";
import { useMemo } from "react";

export interface JsonViewProps {
  value: unknown;
  className?: string;
  collapsed?: boolean;
}

export function JsonView({ value, className, collapsed = false }: JsonViewProps) {
  const text = useMemo(() => {
    try {
      return JSON.stringify(value, null, collapsed ? 0 : 2);
    } catch {
      return String(value);
    }
  }, [value, collapsed]);

  return (
    <pre
      className={cn(
        "max-h-96 overflow-auto rounded-md border border-border bg-bg-2 p-2 font-mono text-[11px] leading-snug text-muted",
        className,
      )}
    >
      {text}
    </pre>
  );
}
