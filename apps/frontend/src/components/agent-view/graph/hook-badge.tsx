import { cn } from "@/lib/utils";

interface HookBadgeProps {
  label: "forward_in" | "forward_out";
  active: boolean;
  doc: string;
}

export function HookBadge({ label, active, doc }: HookBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex rounded border px-1.5 py-0.5 font-mono text-[10px]",
        active
          ? "border-ok bg-ok/15 text-text"
          : "border-border bg-bg-1 text-muted",
      )}
      title={doc}
      aria-label={`${label} hook ${active ? "active" : "inactive"}: ${doc}`}
    >
      {label}
    </span>
  );
}
