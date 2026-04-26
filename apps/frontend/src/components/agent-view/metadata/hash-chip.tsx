import { cn, truncateMiddle } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";

interface HashChipProps {
  hash: string | null | undefined;
  className?: string;
  asButton?: boolean;
}

function hashToHue(value: string): number {
  let acc = 0;
  for (let i = 0; i < value.length; i++) {
    acc = (acc * 33 + value.charCodeAt(i)) % 360;
  }
  return acc;
}

export function hashColor(hash: string): { background: string; border: string } {
  const hue = hashToHue(hash);
  return {
    background: `hsl(${hue} 65% 18%)`,
    border: `hsl(${hue} 70% 36%)`,
  };
}

export function HashChip({ hash, className, asButton = true }: HashChipProps) {
  const [copied, setCopied] = useState(false);
  const normalized = typeof hash === "string" && hash.length > 0 ? hash : null;
  const colors = useMemo(
    () => (normalized ? hashColor(normalized) : { background: "", border: "" }),
    [normalized],
  );

  useEffect(() => {
    if (!copied) return;
    const t = window.setTimeout(() => setCopied(false), 900);
    return () => window.clearTimeout(t);
  }, [copied]);

  if (!normalized) {
    return (
      <span
        className={cn(
          "rounded-full border border-border bg-bg-2 px-2 py-0.5 text-[11px] text-muted",
          className,
        )}
      >
        —
      </span>
    );
  }

  if (!asButton) {
    return (
      <span
        title={normalized}
        className={cn("rounded-full border px-2 py-0.5 font-mono text-[11px] text-text", className)}
        style={{ backgroundColor: colors.background, borderColor: colors.border }}
      >
        {truncateMiddle(normalized, 6)}
      </span>
    );
  }

  return (
    <button
      type="button"
      title={normalized}
      aria-label={`copy hash ${normalized}`}
      className={cn(
        "rounded-full border px-2 py-0.5 font-mono text-[11px] text-text transition-colors hover:brightness-110",
        className,
      )}
      style={{ backgroundColor: colors.background, borderColor: colors.border }}
      onClick={async () => {
        await navigator.clipboard.writeText(normalized);
        setCopied(true);
      }}
    >
      {copied ? "copied" : truncateMiddle(normalized, 6)}
    </button>
  );
}
