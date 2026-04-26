import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface FieldRowProps {
  name: string;
  type: string;
  description: string;
  system: boolean;
  onValues?: () => void;
}

export function FieldRow({ name, type, description, system, onValues }: FieldRowProps) {
  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-center gap-1 rounded border border-border bg-bg-2 px-2 py-1 text-[11px]">
      <div className="min-w-0">
        <div className="truncate text-text">
          {name} <span className="text-muted">({type})</span>
        </div>
        <div className="truncate text-muted" title={description}>
          {description || "no description"}
        </div>
      </div>
      <span
        className={cn(
          "rounded px-1 py-0.5 text-[10px] font-medium",
          system ? "bg-warn/30 text-warn" : "bg-accent-dim text-accent",
        )}
      >
        {system ? "S" : "U"}
      </span>
      {onValues ? (
        <Button variant="ghost" size="sm" className="h-5 px-1 text-[10px]" onClick={onValues}>
          values
        </Button>
      ) : null}
    </div>
  );
}
