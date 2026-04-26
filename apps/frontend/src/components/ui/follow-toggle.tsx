import { cn } from "@/lib/utils";

export interface FollowToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  className?: string;
}

export function FollowToggle({ checked, onChange, label, className }: FollowToggleProps) {
  return (
    <label
      className={cn(
        "inline-flex select-none items-center gap-1.5 text-[0.72rem] text-muted hover:text-text",
        className,
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3 w-3 cursor-pointer accent-accent"
      />
      {label}
    </label>
  );
}
