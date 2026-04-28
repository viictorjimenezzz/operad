import { hashColor } from "@/lib/hash-color";
import { cn, truncateMiddle } from "@/lib/utils";
import * as Tooltip from "@radix-ui/react-tooltip";
import { Check, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";

export const HASH_KEYS = [
  "hash_model",
  "hash_prompt",
  "hash_input",
  "hash_output_schema",
  "hash_config",
  "hash_graph",
  "hash_content",
] as const;

export type HashKey = (typeof HASH_KEYS)[number];

export interface HashRowProps {
  current: Partial<Record<HashKey, string | null>>;
  previous?: Partial<Record<HashKey, string | null>>;
  size?: "sm" | "md";
  variant?: "full" | "compact" | "strip";
  onCopy?: (key: HashKey, value: string) => void;
}

export function HashRow({
  current,
  previous,
  size = "sm",
  variant = "full",
  onCopy,
}: HashRowProps) {
  if (variant === "compact") {
    return (
      <Tooltip.Provider delayDuration={0}>
        <HashCompact current={current} previous={previous} onCopy={onCopy} />
      </Tooltip.Provider>
    );
  }
  if (variant === "strip") {
    return (
      <Tooltip.Provider delayDuration={0}>
        <HashStrip current={current} previous={previous} />
      </Tooltip.Provider>
    );
  }
  return (
    <Tooltip.Provider delayDuration={0}>
      <div role="list" className="flex flex-wrap gap-1.5">
        {HASH_KEYS.map((key) => {
          const value = current[key] ?? null;
          const previousValue = previous?.[key];
          const changed = previous != null && previousValue !== value;
          return (
            <HashChip
              key={key}
              keyName={key}
              value={value}
              changed={changed}
              size={size}
              onCopy={onCopy}
            />
          );
        })}
      </div>
    </Tooltip.Provider>
  );
}

function HashCompact({
  current,
  previous,
  onCopy,
}: {
  current: Partial<Record<HashKey, string | null>>;
  previous?: Partial<Record<HashKey, string | null>>;
  onCopy?: ((key: HashKey, value: string) => void) | undefined;
}) {
  const value = current.hash_content ?? null;
  const monogram = value ? truncateMiddle(value, 12) : "—";
  const changed = HASH_KEYS.some((key) => previous != null && previous[key] !== current[key]);

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-1 rounded border border-border bg-bg-2 px-1.5 py-0.5 font-mono text-[10px] text-muted transition-colors hover:border-border-strong hover:text-text",
            changed && "border-[--color-warn] ring-1 ring-[--color-warn]/40",
          )}
          aria-label="hash drift summary"
        >
          <span
            aria-hidden
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: value ? hashColor(value) : "var(--color-muted-2)" }}
          />
          <span>{monogram}</span>
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          sideOffset={6}
          className="z-50 w-[300px] rounded-md border border-border-strong bg-bg-1 px-2 py-1.5 text-[11px] shadow-[var(--shadow-popover)]"
        >
          <div className="mb-1 text-[10px] uppercase tracking-[0.06em] text-muted-2">
            Reproducibility hashes
          </div>
          <HashTooltipRows current={current} previous={previous} onCopy={onCopy} />
          <Tooltip.Arrow className="fill-bg-1" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function HashStrip({
  current,
  previous,
}: {
  current: Partial<Record<HashKey, string | null>>;
  previous?: Partial<Record<HashKey, string | null>>;
}) {
  return (
    <div role="list" aria-label="hash drift strip" className="inline-flex w-[60px] items-center gap-1">
      {HASH_KEYS.map((key) => {
        const value = current[key] ?? null;
        const changed = previous != null && previous[key] !== value;
        return (
          <span
            key={key}
            role="listitem"
            aria-label={`${key} hash drift`}
            className={cn(
              "inline-flex h-2 w-2 items-center justify-center rounded-full bg-bg-3",
              changed && "ring-1 ring-[--color-warn] ring-offset-1 ring-offset-bg-1",
            )}
          >
            <span
              className={cn("h-1.5 w-1.5 rounded-full", changed && "animate-pulse")}
              style={{ background: value ? hashColor(value) : "var(--color-muted-2)" }}
            />
          </span>
        );
      })}
    </div>
  );
}

function HashTooltipRows({
  current,
  previous,
  onCopy,
}: {
  current: Partial<Record<HashKey, string | null>>;
  previous?: Partial<Record<HashKey, string | null>>;
  onCopy?: ((key: HashKey, value: string) => void) | undefined;
}) {
  const [copied, setCopied] = useState<HashKey | null>(null);

  const copyValue = (keyName: HashKey, value: string | null) => {
    if (!value) return;
    onCopy?.(keyName, value);
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(value).catch(() => undefined);
    }
    setCopied(keyName);
    setTimeout(() => setCopied(null), 900);
  };

  return (
    <div className="space-y-1">
      {HASH_KEYS.map((keyName) => {
        const value = current[keyName] ?? null;
        const changed = previous != null && previous[keyName] !== value;
        const short = value ? truncateMiddle(value, 12) : "—";
        return (
          <div key={keyName} className="flex items-center gap-2">
            <span
              className={cn(
                "w-[155px] truncate font-mono text-[10px] text-muted",
                changed && "font-semibold text-[--color-warn]",
              )}
            >
              {changed ? "Δ " : ""}
              {keyName}: {short}
            </span>
            {value ? (
              <button
                type="button"
                onClick={() => copyValue(keyName, value)}
                className="inline-flex items-center gap-1 rounded border border-border bg-bg-2 px-1.5 py-0.5 text-[10px] text-muted transition-colors hover:border-border-strong hover:text-text"
                aria-label={`copy ${keyName}`}
              >
                {copied === keyName ? (
                  <Check size={11} className="text-[--color-ok]" />
                ) : (
                  <Copy size={11} />
                )}
                {copied === keyName ? "copied" : "copy"}
              </button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function HashChip({
  keyName,
  value,
  changed,
  size,
  onCopy,
}: {
  keyName: HashKey;
  value: string | null;
  changed: boolean;
  size: "sm" | "md";
  onCopy?: ((key: HashKey, value: string) => void) | undefined;
}) {
  const [copied, setCopied] = useState(false);
  const monogram = value ? truncateMiddle(value, 12) : "—";
  const dotSize = size === "md" ? "h-2 w-2" : "h-1.5 w-1.5";
  const textSize = size === "md" ? "text-[11px]" : "text-[10px]";

  const copyValue = () => {
    if (!value) return;
    onCopy?.(keyName, value);
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(value).catch(() => undefined);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 900);
  };

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          role="listitem"
          className={cn(
            "inline-flex items-center gap-1 rounded border border-border bg-bg-2 px-1.5 py-0.5 font-mono text-muted transition-colors hover:border-border-strong hover:text-text",
            textSize,
            changed && "border-[--color-warn] ring-1 ring-[--color-warn]/40",
          )}
          aria-label={`${keyName} hash`}
        >
          <span
            aria-hidden
            className={cn("rounded-full", dotSize)}
            style={{ background: value ? hashColor(value) : "var(--color-muted-2)" }}
          />
          <span className="max-w-28 truncate">{monogram}</span>
          {changed ? <RotateCcw size={10} className="text-[--color-warn]" /> : null}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          sideOffset={6}
          className="z-50 max-w-[300px] rounded-md border border-border-strong bg-bg-1 px-2 py-1.5 text-[11px] shadow-[var(--shadow-popover)]"
        >
          <div className="mb-1 text-[10px] uppercase tracking-[0.06em] text-muted-2">{keyName}</div>
          <div className="font-mono text-text">{value ?? "—"}</div>
          {value ? (
            <button
              type="button"
              onClick={copyValue}
              className="mt-1 inline-flex items-center gap-1 rounded border border-border bg-bg-2 px-1.5 py-0.5 text-[10px] text-muted transition-colors hover:border-border-strong hover:text-text"
            >
              {copied ? <Check size={11} className="text-[--color-ok]" /> : <Copy size={11} />}
              {copied ? "copied" : "copy"}
            </button>
          ) : null}
          <Tooltip.Arrow className="fill-bg-1" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
