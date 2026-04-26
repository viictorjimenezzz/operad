import { hashColor } from "@/lib/hash-color";
import { cn, truncateMiddle } from "@/lib/utils";
import { useMemo } from "react";

export interface HashTagProps {
  /** Source value used both for the dot color and (optionally) display. */
  hash: string | null | undefined;
  /** Label rendered next to the dot. Defaults to truncated hash. */
  label?: string;
  /** Extra label rendered with the muted color (e.g. for run id under class name). */
  sub?: string;
  size?: "sm" | "md" | "lg";
  /** Render only the colored dot — no text. */
  dotOnly?: boolean;
  /** Render label as monospace (use for raw hashes / paths). */
  mono?: boolean;
  className?: string;
  title?: string;
}

const DOT_SIZE: Record<NonNullable<HashTagProps["size"]>, number> = {
  sm: 6,
  md: 8,
  lg: 10,
};

const TEXT_CLASS: Record<NonNullable<HashTagProps["size"]>, string> = {
  sm: "text-[11px]",
  md: "text-sm",
  lg: "text-base",
};

export function HashTag({
  hash,
  label,
  sub,
  size = "md",
  dotOnly = false,
  mono = false,
  className,
  title,
}: HashTagProps) {
  const dotPx = DOT_SIZE[size];
  const color = useMemo(() => (hash ? hashColor(hash) : "var(--color-muted-2)"), [hash]);
  const text = label ?? (hash ? truncateMiddle(hash, 10) : "—");

  return (
    <span
      title={title ?? hash ?? undefined}
      className={cn("inline-flex items-center gap-2", className)}
    >
      <span
        aria-hidden
        className="flex-shrink-0 rounded-full"
        style={{
          width: dotPx,
          height: dotPx,
          background: color,
          boxShadow: hash ? "0 0 0 1px rgba(255,255,255,0.06)" : undefined,
        }}
      />
      {dotOnly ? null : (
        <span className={cn("min-w-0 truncate", TEXT_CLASS[size], mono && "font-mono")}>
          {text}
          {sub != null ? <span className="ml-1.5 text-[10px] text-muted-2">{sub}</span> : null}
        </span>
      )}
    </span>
  );
}
