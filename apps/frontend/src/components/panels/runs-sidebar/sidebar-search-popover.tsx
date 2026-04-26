import { IconButton } from "@/components/ui";
import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface SidebarSearchPopoverProps {
  value: string;
  onChange: (v: string) => void;
}

/**
 * Search icon that, when clicked, expands an inline input. Esc collapses.
 */
export function SidebarSearchPopover({ value, onChange }: SidebarSearchPopoverProps) {
  const [open, setOpen] = useState(value.trim().length > 0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (open) {
    return (
      <div className="flex h-8 flex-1 items-center gap-1.5 rounded-lg border border-border-strong bg-bg-2 px-2 ring-2 ring-[--color-accent-dim]">
        <Search size={13} className="flex-shrink-0 text-muted-2" />
        <input
          ref={inputRef}
          value={value}
          placeholder="search class, id, path…"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              onChange("");
              setOpen(false);
            }
          }}
          className="min-w-0 flex-1 bg-transparent text-[13px] text-text outline-none placeholder:text-muted-2"
        />
        <button
          type="button"
          aria-label="close search"
          onClick={() => {
            onChange("");
            setOpen(false);
          }}
          className="flex-shrink-0 rounded p-1 text-muted-2 hover:text-text"
        >
          <X size={12} />
        </button>
      </div>
    );
  }
  return (
    <IconButton
      aria-label="search runs"
      onClick={() => setOpen(true)}
      title="search (cmd+k)"
      size="sm"
    >
      <Search size={13} />
    </IconButton>
  );
}
