import { cn } from "@/lib/utils";

interface ScriptOriginChipProps {
  script: string | null | undefined;
  className?: string;
}

export function ScriptOriginChip({ script, className }: ScriptOriginChipProps) {
  const raw = script ?? "";
  const label = raw ? (raw.split("/").pop() ?? raw) : "unknown";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border border-border bg-bg-2 px-2 py-0.5 text-[11px] text-muted",
        className,
      )}
      title={raw || "script path unavailable"}
    >
      {label}
    </span>
  );
}
