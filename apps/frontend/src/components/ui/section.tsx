import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { type ReactNode, useState } from "react";

export interface SectionProps {
  title: string;
  summary?: ReactNode;
  badge?: ReactNode;
  defaultOpen?: boolean;
  disabled?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * Accordion-capable container. Header is always visible; body animates open.
 * When `disabled` is true the chevron is muted and clicks are no-ops — used
 * for sections whose data is known empty (e.g. "drift needs 2+ invocations").
 */
export function Section({
  title,
  summary,
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
        "rounded-xl border border-border bg-bg-1 shadow-[var(--shadow-card-soft)] transition-colors",
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
          "flex w-full items-center gap-3 px-4 py-3 text-left",
          disabled ? "cursor-default" : "cursor-pointer",
        )}
      >
        <ChevronRight
          size={14}
          className={cn(
            "flex-shrink-0 text-muted-2 transition-transform duration-150 ease-out",
            expanded && "rotate-90",
          )}
        />
        <h3 className="m-0 flex-shrink-0 text-sm font-medium text-text">{title}</h3>
        {summary != null ? (
          <span className="ml-1 min-w-0 flex-1 truncate text-[13px] text-muted">{summary}</span>
        ) : (
          <span className="flex-1" />
        )}
        {badge}
      </button>
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
            <div className="border-t border-border px-4 py-4">{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
