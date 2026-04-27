import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import { Fragment, type HTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";

/**
 * Slim W&B-style breadcrumb row. Each crumb may be a link or plain text;
 * separators are chevrons. Right side accepts trailing actions.
 */
export interface BreadcrumbItem {
  label: ReactNode;
  to?: string;
  /** Mono-render the label (used for hashes / run ids). */
  mono?: boolean;
}

export interface BreadcrumbProps extends HTMLAttributes<HTMLDivElement> {
  items: BreadcrumbItem[];
  trailing?: ReactNode;
}

export function Breadcrumb({ items, trailing, className, ...rest }: BreadcrumbProps) {
  return (
    <div
      className={cn(
        "flex h-9 items-center gap-1.5 border-b border-border bg-bg px-3 text-[12px]",
        className,
      )}
      {...rest}
    >
      {items.map((it, i) => {
        const last = i === items.length - 1;
        const text = (
          <span
            className={cn(
              it.mono ? "font-mono text-[11px]" : "",
              last ? "text-text" : "text-muted",
            )}
          >
            {it.label}
          </span>
        );
        return (
          <Fragment key={i}>
            {it.to ? (
              <Link
                to={it.to}
                className="text-muted transition-colors hover:text-text"
                aria-current={last ? "page" : undefined}
              >
                {text}
              </Link>
            ) : (
              text
            )}
            {!last ? (
              <ChevronRight aria-hidden size={12} className="flex-shrink-0 text-muted-2" />
            ) : null}
          </Fragment>
        );
      })}
      {trailing != null ? (
        <div className="ml-auto flex items-center gap-3">{trailing}</div>
      ) : null}
    </div>
  );
}
