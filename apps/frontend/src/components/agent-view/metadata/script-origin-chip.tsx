import { cn } from "@/lib/utils";

interface ScriptOriginChipProps {
  script: string | null | undefined;
  className?: string;
}

function basename(value: string): string {
  const parts = value.split(/[\\/]/g);
  const last = parts[parts.length - 1];
  return last && last.length > 0 ? last : value;
}

export function ScriptOriginChip({ script, className }: ScriptOriginChipProps) {
  if (!script) {
    return (
      <span className={cn("rounded-full border border-border bg-bg-2 px-2 py-0.5 text-[11px] text-muted", className)}>
        script: —
      </span>
    );
  }
  return (
    <span
      title={script}
      className={cn(
        "inline-flex items-center rounded-full border border-border bg-bg-2 px-2 py-0.5 font-mono text-[11px] text-muted",
        className,
      )}
    >
      {basename(script)}
    </span>
  );
}
