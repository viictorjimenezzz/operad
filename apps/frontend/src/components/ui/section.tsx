import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { type ReactNode, useState } from "react";

export interface SectionProps {
  title: string;
  /**
   * Inline preview rendered next to the title when collapsed. Single line, truncates.
   * Use this for at-a-glance hints; use `succinct` for actual data rows.
   */
  summary?: ReactNode;
  /**
   * Multi-line content rendered below the header when collapsed. Unlike `summary`,
   * `succinct` is meant to carry real information so the collapsed state is
   * informative rather than just a hint. Hidden when expanded.
   */
  succinct?: ReactNode;
  badge?: ReactNode;
  defaultOpen?: boolean;
  disabled?: boolean;
  children: ReactNode;
  className?: string;
}

export function Section({
  title,
  summary,
  succinct,
  badge,
  defaultOpen = false,
  disabled = false,
  className,
  children,
}: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const expanded = open && !disabled;

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-bg-1 transition-colors",
        expanded ? "border-border-strong" : "",
        disabled ? "opacity-60" : "hover:border-border-strong",
        className,
      )}
    >
      <button
        type="button"
        aria-expanded={expanded}
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-3 px-3 py-2 text-left",
          disabled ? "cursor-default" : "cursor-pointer",
        )}
      >
        <ChevronRight
          size={13}
          className={cn(
            "flex-shrink-0 text-muted-2 transition-transform duration-150 ease-out",
            expanded && "rotate-90",
          )}
        />
        <h3 className="m-0 flex-shrink-0 text-[13px] font-medium text-text">{title}</h3>
        {summary != null ? (
          <span className="ml-1 min-w-0 flex-1 truncate text-[12px] text-muted">{summary}</span>
        ) : (
          <span className="flex-1" />
        )}
        {badge}
      </button>
      {succinct != null && !expanded ? (
        <div className="border-t border-border/60 px-3 py-2">{succinct}</div>
      ) : null}
      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-border px-3 py-3">{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
