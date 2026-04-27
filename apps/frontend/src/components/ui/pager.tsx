import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { HTMLAttributes } from "react";

/**
 * "1-10 of 222 [<] [>]" — the W&B sidebar pager.
 */
export interface PagerProps extends HTMLAttributes<HTMLDivElement> {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pager({ page, pageSize, total, onPageChange, className, ...rest }: PagerProps) {
  const start = total === 0 ? 0 : page * pageSize + 1;
  const end = Math.min(total, (page + 1) * pageSize);
  const lastPage = Math.max(0, Math.ceil(total / pageSize) - 1);
  const canPrev = page > 0;
  const canNext = page < lastPage;

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-2 border-t border-border bg-bg-1 px-2 py-1.5 text-[11px] text-muted-2",
        className,
      )}
      {...rest}
    >
      <button
        type="button"
        disabled={!canPrev}
        onClick={() => canPrev && onPageChange(page - 1)}
        className={cn(
          "flex h-5 w-5 items-center justify-center rounded transition-colors",
          canPrev ? "hover:bg-bg-3 hover:text-text" : "cursor-not-allowed opacity-40",
        )}
        aria-label="previous page"
      >
        <ChevronLeft size={12} />
      </button>
      <span className="font-mono tabular-nums">
        {start}-{end} of {total}
      </span>
      <button
        type="button"
        disabled={!canNext}
        onClick={() => canNext && onPageChange(page + 1)}
        className={cn(
          "flex h-5 w-5 items-center justify-center rounded transition-colors",
          canNext ? "hover:bg-bg-3 hover:text-text" : "cursor-not-allowed opacity-40",
        )}
        aria-label="next page"
      >
        <ChevronRight size={12} />
      </button>
    </div>
  );
}
