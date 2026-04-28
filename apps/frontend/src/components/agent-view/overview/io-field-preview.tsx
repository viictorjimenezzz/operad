import { Eyebrow, FieldTree, IconButton } from "@/components/ui";
import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";

export interface IOFieldPreviewProps {
  label: string;
  data: unknown;
  /** Optional descriptions keyed by field path. */
  descriptions?: Record<string, string> | undefined;
  /** Whether the preview starts expanded. */
  defaultExpanded?: boolean;
  /** Optional right-aligned slot in the preview header. */
  right?: ReactNode;
  className?: string;
}

export function IOFieldPreview({
  label,
  data,
  descriptions,
  defaultExpanded = false,
  right,
  className,
}: IOFieldPreviewProps) {
  const [open, setOpen] = useState(defaultExpanded);
  const empty = data === null || data === undefined;

  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-xl border border-border bg-bg-2 transition-colors",
        open && "border-border-strong",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
        <Eyebrow>{label}</Eyebrow>
        <div className="flex items-center gap-1">
          {right}
          {!empty ? (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="rounded px-2 py-1 text-[11px] text-muted transition-colors hover:bg-bg-3 hover:text-text"
            >
              {open ? "preview" : "show full"}
            </button>
          ) : null}
          <IconButton
            aria-label={open ? `collapse ${label}` : `expand ${label}`}
            onClick={() => setOpen((v) => !v)}
            disabled={empty}
            size="sm"
          >
            <ChevronDown
              size={13}
              className={cn("transition-transform duration-150 ease-out", open && "rotate-180")}
            />
          </IconButton>
        </div>
      </div>
      <div className="min-h-0 flex-1 px-3 py-2">
        {empty ? (
          <div className="text-[12px] text-muted-2">no payload captured</div>
        ) : open ? (
          <AnimatePresence mode="wait">
            <motion.div
              key="full"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.15 }}
              className="max-h-[420px] overflow-auto"
            >
              <FieldTree
                data={data}
                defaultDepth={2}
                truncateStrings={false}
                layout="stacked"
                {...(descriptions ? { descriptions } : {})}
              />
            </motion.div>
          </AnimatePresence>
        ) : (
          <FieldTree data={data} preview />
        )}
      </div>
    </div>
  );
}
