import { useUrlHash } from "@/hooks/use-url-state";
import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

export interface CollapsibleSectionProps {
  id: string;
  label: string;
  preview: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function CollapsibleSection({
  id,
  label,
  preview,
  defaultOpen,
  children,
}: CollapsibleSectionProps) {
  const [hash] = useUrlHash();
  const bodyId = useId();
  const hashOpen = hash === `#section=${id}`;
  const [open, setOpen] = useState(() => Boolean(defaultOpen || hashOpen));

  useEffect(() => {
    if (hashOpen) setOpen(true);
  }, [hashOpen]);

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-bg-1">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((curr) => !curr)}
        className="flex min-h-10 w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-bg-2/50"
      >
        <ChevronDown
          size={14}
          className={cn("flex-shrink-0 text-muted-2 transition-transform", open && "rotate-180")}
        />
        <span className="font-medium text-[13px] text-text">{label}</span>
        <span className="min-w-0 flex-1 truncate text-[12px] text-muted-2">{preview}</span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={bodyId}
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15, ease: [0.2, 0.8, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-border p-3">{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}
