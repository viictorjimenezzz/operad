import { Button } from "@/components/ui/button";
import { hashToColor } from "@/lib/hash-color";
import { cn, truncateMiddle } from "@/lib/utils";
import { Copy } from "lucide-react";
import { useState } from "react";

interface HashChipProps {
  value: string | null | undefined;
  className?: string;
}

export function HashChip({ value, className }: HashChipProps) {
  const [copied, setCopied] = useState(false);
  const text = value ?? "";

  const onCopy = async () => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };

  if (!text) {
    return (
      <span
        className={cn(
          "rounded border border-border px-1.5 py-0.5 text-[11px] text-muted",
          className,
        )}
      >
        —
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5",
        className,
      )}
      style={{ backgroundColor: hashToColor(text, 0.2) }}
    >
      <code className="font-mono text-[11px] text-text">{truncateMiddle(text, 12)}</code>
      <Button
        size="icon"
        variant="ghost"
        className="h-4 w-4 text-muted hover:text-text"
        onClick={onCopy}
        aria-label="copy hash"
      >
        <Copy className="h-3 w-3" />
      </Button>
      {copied ? <span className="text-[10px] text-ok">copied</span> : null}
    </span>
  );
}
