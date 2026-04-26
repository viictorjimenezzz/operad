import { JsonView } from "@/components/ui/json-view";
import { cn } from "@/lib/utils";

interface ValueDetailProps {
  value: unknown;
  className?: string;
}

export function ValueDetail({ value, className }: ValueDetailProps) {
  if (typeof value === "string") {
    return (
      <div className={cn("rounded border border-border bg-bg-2 p-2", className)}>
        <div className="mb-1 text-[10px] uppercase tracking-[0.08em] text-muted">text</div>
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text">
          {value}
        </pre>
      </div>
    );
  }

  return (
    <div className={cn("rounded border border-border bg-bg-2 p-2", className)}>
      <div className="mb-1 text-[10px] uppercase tracking-[0.08em] text-muted">json tree</div>
      <JsonView value={value} className="max-h-64" />
    </div>
  );
}
